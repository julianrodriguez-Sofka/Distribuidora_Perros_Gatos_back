-- Create default admin user
-- Password: Admin@2024
-- Email: admin@distribuidora.com

-- IMPORTANTE: Este script crea el usuario en SQL pero el hash debe ser generado
-- usando bcrypt desde Python para garantizar compatibilidad.
-- 
-- Para crear/actualizar el usuario admin correctamente, ejecuta:
--   docker exec -i distribuidora-api python /app/create_admin_user.py
--
-- O desde la carpeta backend/api:
--   python create_admin_user.py

USE distribuidora_db;
GO

PRINT 'Para crear el usuario administrador correctamente, ejecuta:';
PRINT '  docker exec -i distribuidora-api python /app/create_admin_user.py';
PRINT '';
PRINT 'El script Python garantiza que el hash de bcrypt sea compatible con la aplicación.';
GO
