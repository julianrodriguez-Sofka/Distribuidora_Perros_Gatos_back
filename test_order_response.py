#!/usr/bin/env python3
"""Test script to verify _pedido_to_response function"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'api'))

from app.database import SessionLocal
from app.routers.orders import _pedido_to_response
from app.models import Pedido
import json

db = SessionLocal()
try:
    p = db.query(Pedido).filter(Pedido.id == 8).first()
    if not p:
        print("ERROR: Pedido 8 not found")
        sys.exit(1)
    
    result = _pedido_to_response(db, p)
    
    print("=" * 60)
    print("RESULTADO COMPLETO:")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
    
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE CAMPOS:")
    print("=" * 60)
    print(f"clienteNombre: {result.get('clienteNombre')}")
    print(f"clienteEmail: {result.get('clienteEmail')}")
    print(f"clienteTelefono: {result.get('clienteTelefono')}")
    print(f"direccion_entrega: {result.get('direccion_entrega')}")
    print(f"telefono_contacto: {result.get('telefono_contacto')}")
    print(f"metodo_pago: {result.get('metodo_pago')}")
    print(f"subtotal: {result.get('subtotal')}")
    print(f"costo_envio: {result.get('costo_envio')}")
    print(f"total: {result.get('total')}")
    print(f"items count: {len(result.get('items', []))}")
    if result.get('items'):
        print(f"items[0].nombre: {result.get('items', [{}])[0].get('nombre')}")
    
    # Verify all required fields are present
    required_fields = [
        'clienteNombre', 'clienteEmail', 'direccion_entrega', 
        'telefono_contacto', 'metodo_pago', 'subtotal', 'costo_envio'
    ]
    missing = [f for f in required_fields if not result.get(f)]
    if missing:
        print(f"\n❌ CAMPOS FALTANTES: {missing}")
    else:
        print("\n✅ TODOS LOS CAMPOS ESTÁN PRESENTES")
        
finally:
    db.close()

