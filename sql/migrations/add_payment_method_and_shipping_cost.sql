-- Migration: Add payment method and shipping cost fields to Pedidos table
-- Date: 2025-11-29
-- Description: Adds metodo_pago, costo_envio, and subtotal columns to support detailed order breakdown

-- Add subtotal column
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[Pedidos]') AND name = 'subtotal')
BEGIN
    ALTER TABLE [dbo].[Pedidos]
    ADD subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0;
    PRINT 'Added subtotal column to Pedidos table';
END
ELSE
BEGIN
    PRINT 'subtotal column already exists';
END
GO

-- Add costo_envio column
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[Pedidos]') AND name = 'costo_envio')
BEGIN
    ALTER TABLE [dbo].[Pedidos]
    ADD costo_envio NUMERIC(10, 2) NOT NULL DEFAULT 0;
    PRINT 'Added costo_envio column to Pedidos table';
END
ELSE
BEGIN
    PRINT 'costo_envio column already exists';
END
GO

-- Add metodo_pago column
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID(N'[dbo].[Pedidos]') AND name = 'metodo_pago')
BEGIN
    ALTER TABLE [dbo].[Pedidos]
    ADD metodo_pago VARCHAR(50) NULL;
    PRINT 'Added metodo_pago column to Pedidos table';
END
ELSE
BEGIN
    PRINT 'metodo_pago column already exists';
END
GO

-- Update existing records: set subtotal = total and costo_envio = 0 for backward compatibility
UPDATE [dbo].[Pedidos]
SET subtotal = total,
    costo_envio = 0
WHERE subtotal = 0 OR subtotal IS NULL;
GO

PRINT 'Migration completed successfully';

