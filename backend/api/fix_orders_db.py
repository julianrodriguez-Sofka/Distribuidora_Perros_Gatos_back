import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Add subtotal
    try:
        db.execute(text("ALTER TABLE Pedidos ADD subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0"))
        db.commit()
        print("Added subtotal")
    except Exception as e:
        print(f"subtotal: {str(e)[:100]}")
        db.rollback()
    
    # Add costo_envio
    try:
        db.execute(text("ALTER TABLE Pedidos ADD costo_envio NUMERIC(10, 2) NOT NULL DEFAULT 0"))
        db.commit()
        print("Added costo_envio")
    except Exception as e:
        print(f"costo_envio: {str(e)[:100]}")
        db.rollback()
    
    # Add metodo_pago
    try:
        db.execute(text("ALTER TABLE Pedidos ADD metodo_pago VARCHAR(50) NULL"))
        db.commit()
        print("Added metodo_pago")
    except Exception as e:
        print(f"metodo_pago: {str(e)[:100]}")
        db.rollback()
    
    print("Done")
finally:
    db.close()

