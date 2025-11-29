#!/usr/bin/env python3
"""
Script to run the payment method and shipping cost migration
"""
import sys
import os
sys.path.insert(0, '/app')

from app.database import SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    db = SessionLocal()
    try:
        logger.info("Checking if columns exist...")
        
        # Check current columns
        result = db.execute(text("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Pedidos' 
            ORDER BY ORDINAL_POSITION
        """))
        existing_columns = [row[0] for row in result.fetchall()]
        logger.info(f"Existing columns: {', '.join(existing_columns)}")
        
        # Add subtotal if not exists
        if 'subtotal' not in existing_columns:
            logger.info("Adding subtotal column...")
            db.execute(text("""
                ALTER TABLE [dbo].[Pedidos]
                ADD subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0;
            """))
            db.commit()
            logger.info("Added subtotal column")
        else:
            logger.info("subtotal column already exists")
        
        # Add costo_envio if not exists
        if 'costo_envio' not in existing_columns:
            logger.info("Adding costo_envio column...")
            db.execute(text("""
                ALTER TABLE [dbo].[Pedidos]
                ADD costo_envio NUMERIC(10, 2) NOT NULL DEFAULT 0;
            """))
            db.commit()
            logger.info("Added costo_envio column")
        else:
            logger.info("costo_envio column already exists")
        
        # Add metodo_pago if not exists
        if 'metodo_pago' not in existing_columns:
            logger.info("Adding metodo_pago column...")
            db.execute(text("""
                ALTER TABLE [dbo].[Pedidos]
                ADD metodo_pago VARCHAR(50) NULL;
            """))
            db.commit()
            logger.info("Added metodo_pago column")
        else:
            logger.info("metodo_pago column already exists")
        
        # Update existing records
        logger.info("Updating existing records...")
        db.execute(text("""
            UPDATE [dbo].[Pedidos]
            SET subtotal = total,
                costo_envio = 0
            WHERE subtotal = 0 OR subtotal IS NULL;
        """))
        db.commit()
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Error running migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()

