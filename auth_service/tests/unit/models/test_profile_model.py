import uuid

import pytest

from auth_service.models.profile import Profile


def test_profile_model_instantiation():
    """Test basic instantiation and attribute assignment for Profile model."""
    user_id_val = uuid.uuid4()
    username_val = "test_user"
    first_name_val = "Test"
    last_name_val = "User"
    is_active_val = True

    profile = Profile(
        user_id=user_id_val,
        username=username_val,
        first_name=first_name_val,
        last_name=last_name_val,
        is_active=is_active_val,
    )

    assert profile.user_id == user_id_val
    assert profile.username == username_val
    assert profile.first_name == first_name_val
    assert profile.last_name == last_name_val
    assert profile.is_active == is_active_val

    expected_repr = (
        f"<Profile(user_id='{str(user_id_val)}', username='{username_val}')>"
    )
    assert repr(profile) == expected_repr

    assert hasattr(profile, "created_at")
    assert hasattr(profile, "updated_at")
