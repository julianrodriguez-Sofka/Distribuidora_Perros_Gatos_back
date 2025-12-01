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
        print("✓ Added subtotal column")
    except Exception as e:
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            print("✓ subtotal column already exists")
        else:
            print(f"Error adding subtotal: {e}")
            db.rollback()
    
    # Add costo_envio
    try:
        db.execute(text("ALTER TABLE Pedidos ADD costo_envio NUMERIC(10, 2) NOT NULL DEFAULT 0"))
        db.commit()
        print("✓ Added costo_envio column")
    except Exception as e:
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            print("✓ costo_envio column already exists")
        else:
            print(f"Error adding costo_envio: {e}")
            db.rollback()
    
    # Add metodo_pago
    try:
        db.execute(text("ALTER TABLE Pedidos ADD metodo_pago VARCHAR(50) NULL"))
        db.commit()
        print("✓ Added metodo_pago column")
    except Exception as e:
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            print("✓ metodo_pago column already exists")
        else:
            print(f"Error adding metodo_pago: {e}")
            db.rollback()
    
    # Update existing records
    try:
        db.execute(text("UPDATE Pedidos SET subtotal = total, costo_envio = 0 WHERE subtotal = 0 OR subtotal IS NULL"))
        db.commit()
        print("✓ Updated existing records")
    except Exception as e:
        print(f"Error updating records: {e}")
        db.rollback()
    
    print("Migration completed!")
finally:
    db.close()

