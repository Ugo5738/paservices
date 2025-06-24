import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from gotrue.errors import AuthApiError as SupabaseAPIError
from gotrue.types import UserAttributes
from sqlalchemy.exc import SQLAlchemyError  # Added
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.config import Environment
from auth_service.config import Settings as AppSettingsType  # For type hinting settings
from auth_service.crud import user_crud
from auth_service.db import get_db
from auth_service.dependencies import (
    get_app_settings,
    get_current_supabase_user,
    oauth2_scheme,
)
from auth_service.rate_limiting import (
    LOGIN_LIMIT,
    PASSWORD_RESET_LIMIT,
    REGISTRATION_LIMIT,
    limiter,
)
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.schemas.user_schemas import *
from auth_service.security_audit import *
from auth_service.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth/users",
    tags=["User Authentication"],
)


@router.post("/login", response_model=SupabaseSession, status_code=status.HTTP_200_OK)
@limiter.limit(LOGIN_LIMIT)
async def login_user(
    request: Request,
    login_data: UserLoginRequest,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    settings: AppSettingsType = Depends(get_app_settings),
    # db_session: AsyncSession = Depends(get_db), # Not strictly needed for login unless updating last_login
):
    # Log login attempt using security audit
    log_login_attempt(request, login_data.email)

    # Attempt to log in with Supabase
    try:
        logger.info(f"Attempting to login user with email: {login_data.email}")
        # Call supabase auth sign_in method (authenticate)
        response = await supabase.auth.sign_in_with_password(
            {
                "email": login_data.email,
                "password": login_data.password,
            }
        )
        # Get user and session data
        supa_session = response.session
        supa_user = response.user

        if not supa_user or not supa_session:
            raise SupabaseAPIError("Invalid login credentials", status=401)

        # Check for email confirmation if required by settings
        if (
            settings.SUPABASE_EMAIL_CONFIRMATION_REQUIRED
            and not supa_user.email_confirmed_at
        ):
            log_login_failure(request, login_data.email, "Email not confirmed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not confirmed. Please check your inbox.",
            )

        log_login_success(request, supa_user.id, login_data.email)
        return supa_session
    except SupabaseAPIError as e:
        log_login_failure(request, login_data.email, reason=e.message)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login credentials"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during login for {login_data.email}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login.",
        )


@router.post(
    "/login/magiclink",
    response_model=MagicLinkSentResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(LOGIN_LIMIT, key_func=lambda request: request.client.host)
async def login_magic_link(
    request: Request,
    request_data: MagicLinkLoginRequest,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
):
    logger.info(f"Magic link login attempt for email: {request_data.email}")
    try:
        await supabase.auth.sign_in_with_otp(
            {"email": request_data.email, "options": {}}
        )

        logger.info(f"Magic link successfully requested for {request_data.email}")
        return MagicLinkSentResponse(
            message=f"Magic link sent to {request_data.email}. Please check your inbox."
        )

    except SupabaseAPIError as e:
        logger.warning(
            f"Supabase API error during magic link request for {request_data.email}: {e.message} (Status: {e.status})"
        )
        detail = f"Failed to send magic link: {e.message}"
        http_status_code = status.HTTP_400_BAD_REQUEST
        if e.status and 400 <= e.status < 500:
            http_status_code = e.status
        elif e.status and e.status == 500:
            http_status_code = status.HTTP_502_BAD_GATEWAY
            detail = "Authentication service provider returned an error."

        raise HTTPException(status_code=http_status_code, detail=detail)
    except Exception as e:
        logger.error(
            f"Unexpected error during magic link request for {request_data.email}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while requesting the magic link.",
        )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(REGISTRATION_LIMIT)
async def register_user(
    request: Request,
    user_in: UserCreate,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    db_session: AsyncSession = Depends(get_db),
    settings: AppSettingsType = Depends(get_app_settings),
):
    logger.info(f"Registration attempt for email: {user_in.email}")
    try:
        user_metadata = {
            "username": user_in.username,
            "first_name": user_in.first_name,
            "last_name": user_in.last_name,
        }
        supa_response = await supabase.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
                "options": {"data": user_metadata},
            }
        )
        logger.debug(f"Supabase sign_up response: {supa_response}")

        supa_user = supa_response.user
        supa_session = supa_response.session

        if not supa_user:
            logger.error("Supabase sign_up did not return a user object.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User registration failed: No user object returned from authentication provider.",
            )

        profile_data = ProfileCreate(user_id=supa_user.id, **user_in.model_dump())
        created_profile = await user_crud.create_profile_in_db(
            db_session=db_session, profile_in=profile_data
        )

        if not created_profile:
            logger.error(
                f"Failed to create profile for user_id {supa_user.id} after registration."
            )
            # Here, you might want to attempt to delete the Supabase user to avoid orphaned accounts.
            # await supabase.auth.admin.delete_user(supa_user.id) # Requires admin client
            raise HTTPException(
                status_code=500,
                detail="Failed to create user profile after registration.",
            )

        message = "User registered successfully."
        if (
            settings.SUPABASE_EMAIL_CONFIRMATION_REQUIRED
            and not supa_user.email_confirmed_at
        ):
            message = "User registration initiated. Please check your email to confirm your account."

        log_security_event(
            event_type="registration",
            user_id=supa_user.id,
            request=request,
            status="success",
            detail=message,
        )

        return UserResponse(
            message=message,
            session=supa_session,
            profile=ProfileResponse.model_validate(
                created_profile, from_attributes=True
            ),
        )

    except SupabaseAPIError as e:
        log_security_event(
            event_type="registration",
            request=request,
            status="failure",
            detail=e.message,
            additional_data={"email": user_in.email},
        )
        http_status_code = (
            status.HTTP_409_CONFLICT
            if "already registered" in e.message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=http_status_code, detail=f"Registration failed: {e.message}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during registration for {user_in.email}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration.",
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: SupabaseUser = Depends(get_current_supabase_user),
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
):
    logger.info(f"Logout requested for user: {current_user.id}")

    # Log logout attempt with security audit
    log_security_event(
        event_type="logout", user_id=current_user.id, request=request, status="attempt"
    )

    try:
        await supabase.auth.sign_out(jwt=token)
        log_security_event(
            event_type="logout",
            user_id=current_user.id,
            request=request,
            status="success",
        )
        return MessageResponse(message="Successfully logged out")
    except Exception as e:
        log_security_event(
            event_type="logout",
            user_id=current_user.id,
            request=request,
            status="failure",
            detail=str(e),
        )
        logger.error(
            f"Unexpected error during logout for user {current_user.email}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logout.",
        )


@router.post(
    "/password/reset",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(PASSWORD_RESET_LIMIT, key_func=lambda request: request.client.host)
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    settings_dep: AppSettingsType = Depends(
        get_app_settings
    ),  # Access settings via dependency
):
    logger.info(f"Password reset requested for email: {payload.email}")

    # Log password reset request with security audit
    log_password_reset_request(request, payload.email)

    try:
        # Supabase's reset_password_for_email does not error out if the email doesn't exist.
        # It sends an email if the user exists, otherwise does nothing.
        # This is good for security as it prevents email enumeration.
        await supabase.auth.reset_password_for_email(
            email=payload.email,
            options={"redirect_to": settings_dep.PASSWORD_RESET_REDIRECT_URL},
        )
        # Always return a generic success message to prevent email enumeration
        logger.info(
            f"Password reset process initiated for email: {payload.email} (if user exists)."
        )
        return PasswordResetResponse(
            message="If an account with this email exists, a password reset link has been sent."
        )
    except SupabaseAPIError as e:
        logger.error(
            f"Supabase API error during password reset for {payload.email}: {e.message} (Status: {e.status}, Code: {e.code})",
            exc_info=True,
        )

        # Log failed password reset request (no user_id since this is unauthenticated)
        log_security_event(
            event_type="password_reset_failure",
            request=request,
            status="failure",
            detail=f"API error: {e.message}",
            additional_data={"email": payload.email},
        )

        # Handle specific Supabase errors if necessary, e.g., rate limiting
        if e.status == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset requests. Please try again later.",
            )

        # Handle specific Supabase errors if necessary, e.g., rate limiting
        if e.status == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Password reset request failed: {e.message}",
            )
        # For other Supabase errors, return a generic service unavailable message
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Password reset request failed: {e.message}",  # Or a more generic message
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during password reset for {payload.email}: {e}",
            exc_info=True,
        )

        # Log failed password reset due to unexpected error (no user_id since this is unauthenticated)
        log_security_event(
            event_type="password_reset_failure",
            request=request,
            status="failure",
            detail="Unexpected error",
            additional_data={"email": payload.email},
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while requesting password reset.",
        )


@router.post(
    "/password/update",
    response_model=PasswordUpdateResponse,
    status_code=status.HTTP_200_OK,  # Changed response_model
)
async def update_user_password(
    request: Request,
    payload: PasswordUpdateRequest,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    current_user: SupabaseUser = Depends(
        get_current_supabase_user
    ),  # Removed token dependency
):
    logger.info(f"Password update attempt for user: {current_user.email}")

    # Log password change attempt with security audit
    log_password_change(request, current_user.id, status="attempt")

    try:
        await supabase.auth.update_user(
            attributes=UserAttributes(
                password=payload.new_password
            )  # Removed jwt=token
        )

        # Log successful password change with security audit
        log_password_change(request, current_user.id, status="success")

        logger.info(f"Password updated successfully for user: {current_user.email}")
        return PasswordUpdateResponse(message="Password updated successfully.")
    except SupabaseAPIError as e:
        logger.warning(
            f"Supabase API error during password update for user {current_user.email}: "
            f"{e.message} (Status: {e.status}, Code: {e.code})"
        )

        # Log failed password change with security audit
        log_password_change(
            request, current_user.id, status="failure", detail=f"API error: {e.message}"
        )

        error_detail = f"Password update failed: {e.message}"
        error_status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        if isinstance(e.status, int) and 400 <= e.status < 600:
            error_status_code = e.status

        raise HTTPException(status_code=error_status_code, detail=error_detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during password update for user {current_user.email}: {e}",
            exc_info=True,
        )

        # Log failed password change due to unexpected error
        log_password_change(
            request, current_user.id, status="failure", detail="Unexpected error"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during password update.",
        )


@router.get("/me", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    request_data: UserProfileUpdateRequest,
    current_user: SupabaseUser = Depends(get_current_supabase_user),
    db_session: AsyncSession = Depends(get_db),
):
    """
    Get the profile of the currently authenticated user.
    """
    logger.info(f"Fetching profile for current user: {current_user.id}")

    # Use the user_crud function to get the profile
    profile = await user_crud.get_profile_by_user_id_from_db(
        db_session, current_user.id
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found."
        )

    update_data = request_data.model_dump(exclude_unset=True)
    if not update_data:
        return profile

    if "username" in update_data and update_data["username"] is not None:
        if update_data["username"] != profile.username:
            existing_profile = await user_crud.get_profile_by_username(
                db_session, update_data["username"]
            )
            if existing_profile and existing_profile.user_id != current_user.id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Username '{update_data['username']}' already exists.",
                )

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db_session.flush()
    await db_session.refresh(profile)
    return profile


@router.put("/me", response_model=ProfileResponse, status_code=status.HTTP_200_OK)
async def update_current_user_profile(
    request_data: UserProfileUpdateRequest,
    current_user: SupabaseUser = Depends(get_current_supabase_user),
    db_session: AsyncSession = Depends(get_db),
):
    """
    Update the profile of the currently authenticated user.
    """
    logger.info(
        f"User {current_user.id} attempting to update their profile. Request data (excluding unset): {request_data.model_dump(exclude_unset=True)}"
    )

    # 1. Fetch the current user's profile using the CRUD function
    profile = await user_crud.get_profile_by_user_id_from_db(
        db_session, current_user.id
    )
    if not profile:
        logger.warning(
            f"Profile not found for user {current_user.id} during update attempt."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    update_data = request_data.model_dump(exclude_unset=True)

    # If no data is provided in the request, return the current profile
    if not update_data:
        logger.info(
            f"User {current_user.id}: No update data provided for profile. Returning current profile."
        )
        return ProfileResponse.model_validate(profile)

    # 2. Check for username conflict if username is being updated
    if "username" in update_data and update_data["username"] is not None:
        new_username = str(update_data["username"])  # Ensure it's a string
        # Only check for conflict if the new username is different from the current one
        if new_username != profile.username:
            existing_profile_with_username = await user_crud.get_profile_by_username(
                db_session, new_username
            )
            if (
                existing_profile_with_username
                and existing_profile_with_username.user_id != current_user.id
            ):
                logger.warning(
                    f"User {current_user.id} attempted to update username to '{new_username}', "
                    f"which is already taken by user {existing_profile_with_username.user_id}."
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{new_username}' already exists.",
                )

    # 3. Update profile attributes if they have changed
    changed_fields_count = 0
    for field, value in update_data.items():
        if hasattr(profile, field) and getattr(profile, field) != value:
            setattr(profile, field, value)
            changed_fields_count += 1
            logger.debug(
                f"User {current_user.id}: Profile field '{field}' will be updated to '{value}'"
            )

    # If no actual changes to the profile data, return the current profile
    if changed_fields_count == 0:
        logger.info(
            f"User {current_user.id}: Provided data matches current profile values. No database update performed."
        )
        return ProfileResponse.model_validate(profile)

    # 4. Commit changes (updated_at is handled by SQLAlchemy's onupdate=func.now())
    try:
        await db_session.commit()
        await db_session.refresh(profile)
        logger.info(
            f"User {current_user.id} profile updated successfully. Changed fields: {changed_fields_count}"
        )
    except SQLAlchemyError as e:  # More specific DB error
        await db_session.rollback()
        logger.error(
            f"Database error updating profile for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update profile due to a database error.",
        )
    except Exception as e:  # Catch-all for other unexpected errors
        await db_session.rollback()
        logger.error(
            f"Unexpected error updating profile for user {current_user.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the profile.",
        )

    return ProfileResponse.model_validate(profile)


# --- OAuth Endpoints ---


@router.get("/login/{provider}", response_class=RedirectResponse)
async def oauth_login_initiate(
    provider: OAuthProvider,  # Path parameter, validated by Pydantic enum
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    settings: AppSettingsType = Depends(get_app_settings),
):
    log_security_event(
        event_type="oauth_initiate",
        request=None,
        status="attempt",
        additional_data={"provider": provider.value},
    )
    try:
        oauth_response = await supabase.auth.sign_in_with_oauth(
            provider.value,
            options={"redirect_to": settings.OAUTH_REDIRECT_URI},
        )
        response = RedirectResponse(url=oauth_response.url)
        response.set_cookie(
            key=settings.OAUTH_STATE_COOKIE_NAME,
            value=oauth_response.state,
            httponly=True,
            secure=settings.ENVIRONMENT != Environment.DEVELOPMENT,
            samesite="lax",
            max_age=settings.OAUTH_STATE_COOKIE_MAX_AGE_SECONDS,
            path="/",
        )
        return response
    except Exception as e:
        logger.error(
            f"Error during OAuth initiation for provider {provider.value}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth with provider {provider.value}.",
        )


@router.get("/login/{provider}/callback", response_class=JSONResponse)
async def oauth_login_callback(
    provider: OAuthProvider,  # Path parameter
    request: Request,  # To access query parameters like code, state, error
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    db_session: AsyncSession = Depends(get_db),
    settings: AppSettingsType = Depends(get_app_settings),
):
    auth_code = request.query_params.get("code")
    provider_state = request.query_params.get("state")
    stored_state = request.cookies.get(settings.OAUTH_STATE_COOKIE_NAME)

    # Prepare a response object to clear the cookie in all paths (success or fail)
    response = JSONResponse(content={})
    response.delete_cookie(
        key=settings.OAUTH_STATE_COOKIE_NAME,
        httponly=True,
        secure=settings.ENVIRONMENT != Environment.DEVELOPMENT,
        samesite="lax",
        path="/",
    )

    if not provider_state or provider_state != stored_state:
        log_oauth_event(
            request, provider.value, status="failure", detail="Invalid OAuth state."
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.body = JSONResponse(
            {"detail": "Invalid OAuth state. CSRF check failed or state expired."}
        ).body
        return response

    if not auth_code:
        log_oauth_event(
            request,
            provider.value,
            status="failure",
            detail="Authorization code missing.",
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.body = JSONResponse(
            {"detail": "Authorization code missing from OAuth callback."}
        ).body
        return response

    try:
        supa_session = await supabase.auth.exchange_code_for_session(
            auth_code=auth_code
        )
        supa_user = supa_session.user

        if not supa_user:
            raise Exception(
                "Authentication provider did not return valid user information."
            )

        existing_profile = await user_crud.get_profile_by_user_id_from_db(
            db_session, supa_user.id
        )
        if not existing_profile:
            profile_data = ProfileCreate(
                user_id=supa_user.id,
                email=supa_user.email,
                username=supa_user.email.split("@")[0],
                first_name=supa_user.user_metadata.get("full_name", "").split(" ")[0],
                last_name=" ".join(
                    supa_user.user_metadata.get("full_name", "").split(" ")[1:]
                ),
            )
            await user_crud.create_profile_in_db(db_session, profile_in=profile_data)

        log_oauth_event(request, provider.value, user_id=supa_user.id, status="success")
        response.status_code = status.HTTP_200_OK
        response.body = JSONResponse(supa_session.model_dump(mode="json")).body
        return response

    except SupabaseAPIError as e:
        log_oauth_event(request, provider.value, status="failure", detail=e.message)
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.body = JSONResponse(
            {"detail": f"Authentication provider error: {e.message}"}
        ).body
        return response
    except Exception as e:
        logger.error(
            f"Unexpected error during OAuth callback for {provider.value}: {e}",
            exc_info=True,
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        response.body = JSONResponse(
            {"detail": "An unexpected server error occurred."}
        ).body
        return response


# --- Email Verification Endpoints ---


@router.post(
    "/verify/resend", response_model=MessageResponse, status_code=status.HTTP_200_OK
)
@limiter.limit(PASSWORD_RESET_LIMIT, key_func=lambda request: request.client.host)
async def resend_email_verification(
    request: Request,
    payload: EmailVerificationRequest,
    supabase: AsyncSupabaseClient = Depends(get_supabase_client),
    settings_dep: AppSettingsType = Depends(get_app_settings),
):
    """
    Resend the email verification to a user.

    This endpoint allows users to request a new verification email if the original one was
    not received or has expired. Rate limiting is applied to prevent abuse.
    """
    logger.info(f"Email verification resend requested for email: {payload.email}")

    try:
        # Call Supabase API to resend verification email
        # We use reset_password_for_email with specific options to trigger email verification
        # This ensures compatibility with both sync and async clients in tests
        await supabase.auth.reset_password_for_email(
            email=payload.email,
            options={"email_redirect_to": settings_dep.EMAIL_CONFIRMATION_REDIRECT_URL},
        )

        logger.info(f"Verification email resent successfully to {payload.email}")

        return MessageResponse(
            message="Verification email resent. Please check your inbox."
        )

    except SupabaseAPIError as e:
        # Handle Supabase API errors
        error_message = e.message
        status_code = status.HTTP_400_BAD_REQUEST

        if e.status == 400 and "User not found" in error_message:
            # Don't leak information about which emails exist
            logger.warning(
                f"Attempted verification resend for non-existent email: {payload.email}"
            )
            return MessageResponse(
                message="If your email exists in our system, a verification link has been sent."
            )
        elif e.status == 400 and "Email already confirmed" in error_message:
            logger.info(
                f"Verification resend requested for already verified email: {payload.email}"
            )
            return MessageResponse(
                message="Your email is already verified. You can now log in."
            )
        else:
            logger.error(
                f"Supabase error during verification resend: {e.message} (Status: {e.status})"
            )
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            raise HTTPException(
                status_code=status_code,
                detail=f"Error processing email verification resend: {error_message}",
            )

    except Exception as e:
        logger.error(f"Unexpected error during verification resend: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request.",
        )
