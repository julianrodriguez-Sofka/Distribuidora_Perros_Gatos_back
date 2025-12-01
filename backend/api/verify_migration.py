#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Check columns
    result = db.execute(text("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Pedidos' 
        ORDER BY ORDINAL_POSITION
    """))
    
    print("Columnas en tabla Pedidos:")
    for row in result.fetchall():
        print(f"  - {row[0]} ({row[1]}, NULL={row[2]})")
    
    # Check if new columns exist
    result = db.execute(text("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'Pedidos' 
        AND COLUMN_NAME IN ('subtotal', 'costo_envio', 'metodo_pago')
    """))
    
    new_cols = [r[0] for r in result.fetchall()]
    print(f"\nNuevas columnas encontradas: {', '.join(new_cols) if new_cols else 'NINGUNA'}")
    
    if len(new_cols) == 3:
        print("✓ Migración completada correctamente")
    else:
        print("✗ Faltan columnas en la migración")
        
finally:
    db.close()

