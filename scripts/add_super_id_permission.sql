-- SQL script to add super_id:generate permission and assign it to the dev_client

-- Check if client exists (using UUID v5 with DNS namespace for dev_client)
DO $$
DECLARE
    client_uuid UUID := 'b46276a5-4998-5f7c-9a25-a16a2ffc6b11'; -- This is UUID v5 for 'dev_client'
    client_exists BOOLEAN;
    permission_id UUID;
    role_id UUID;
BEGIN
    -- Check if client exists
    SELECT EXISTS(SELECT 1 FROM app_client WHERE id = client_uuid) INTO client_exists;
    
    IF client_exists THEN
        RAISE NOTICE 'Client with ID % exists, proceeding with permission setup', client_uuid;
        
        -- Insert permission if it doesn't exist
        INSERT INTO permission (name, description)
        VALUES ('super_id:generate', 'Permission to generate Super IDs')
        ON CONFLICT (name) DO NOTHING
        RETURNING id INTO permission_id;
        
        -- If permission_id is NULL, it means the permission already existed, so get its ID
        IF permission_id IS NULL THEN
            SELECT id INTO permission_id FROM permission WHERE name = 'super_id:generate';
            RAISE NOTICE 'Using existing permission with ID %', permission_id;
        ELSE
            RAISE NOTICE 'Created new permission with ID %', permission_id;
        END IF;
        
        -- Insert role if it doesn't exist
        INSERT INTO role (name, description)
        VALUES ('MICROSERVICE', 'Role for internal microservice communication')
        ON CONFLICT (name) DO NOTHING
        RETURNING id INTO role_id;
        
        -- If role_id is NULL, it means the role already existed, so get its ID
        IF role_id IS NULL THEN
            SELECT id INTO role_id FROM role WHERE name = 'MICROSERVICE';
            RAISE NOTICE 'Using existing role with ID %', role_id;
        ELSE
            RAISE NOTICE 'Created new role with ID %', role_id;
        END IF;
        
        -- Assign permission to role
        INSERT INTO role_permission (role_id, permission_id)
        VALUES (role_id, permission_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING;
        
        RAISE NOTICE 'Assigned permission % to role %', permission_id, role_id;
        
        -- Assign role to client
        INSERT INTO app_client_role (app_client_id, role_id)
        VALUES (client_uuid, role_id)
        ON CONFLICT (app_client_id, role_id) DO NOTHING;
        
        RAISE NOTICE 'Assigned role % to client %', role_id, client_uuid;
        
        RAISE NOTICE 'Permission setup completed successfully';
    ELSE
        RAISE EXCEPTION 'Client with ID % does not exist', client_uuid;
    END IF;
END $$;
