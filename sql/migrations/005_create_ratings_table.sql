-- =============================================
-- Migración: Crear tabla de calificaciones de productos
-- Descripción: Sistema de ratings con estrellas (1-5) para productos
-- Autor: Sistema de calificaciones
-- Fecha: 2025-12-01
-- =============================================

USE distribuidora_db;
GO

-- Crear tabla de calificaciones
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ProductoCalificaciones')
BEGIN
    CREATE TABLE ProductoCalificaciones (
        id INT IDENTITY(1,1) PRIMARY KEY,
        producto_id INT NOT NULL,
        usuario_id INT NULL, -- NULL para calificaciones anónimas
        calificacion INT NOT NULL CHECK (calificacion >= 1 AND calificacion <= 5),
        comentario NVARCHAR(500) NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_ProductoCalificaciones_Producto FOREIGN KEY (producto_id) REFERENCES Productos(id) ON DELETE CASCADE,
        CONSTRAINT FK_ProductoCalificaciones_Usuario FOREIGN KEY (usuario_id) REFERENCES Usuarios(id) ON DELETE SET NULL
    );

    -- Índice para búsquedas rápidas por producto
    CREATE INDEX IX_ProductoCalificaciones_Producto ON ProductoCalificaciones(producto_id);
    
    -- Índice para búsquedas por usuario
    CREATE INDEX IX_ProductoCalificaciones_Usuario ON ProductoCalificaciones(usuario_id);
    
    PRINT 'Tabla ProductoCalificaciones creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla ProductoCalificaciones ya existe';
END
GO

-- Crear vista para promedios de calificaciones por producto
IF EXISTS (SELECT * FROM sys.views WHERE name = 'v_PromedioCalificaciones')
    DROP VIEW v_PromedioCalificaciones;
GO

CREATE VIEW v_PromedioCalificaciones AS
SELECT 
    producto_id,
    COUNT(*) as total_calificaciones,
    AVG(CAST(calificacion AS FLOAT)) as promedio_calificacion,
    SUM(CASE WHEN calificacion = 5 THEN 1 ELSE 0 END) as estrellas_5,
    SUM(CASE WHEN calificacion = 4 THEN 1 ELSE 0 END) as estrellas_4,
    SUM(CASE WHEN calificacion = 3 THEN 1 ELSE 0 END) as estrellas_3,
    SUM(CASE WHEN calificacion = 2 THEN 1 ELSE 0 END) as estrellas_2,
    SUM(CASE WHEN calificacion = 1 THEN 1 ELSE 0 END) as estrellas_1
FROM ProductoCalificaciones
GROUP BY producto_id;
GO

PRINT 'Sistema de calificaciones configurado exitosamente';
GO
