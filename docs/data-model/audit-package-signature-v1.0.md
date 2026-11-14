# Firma detached Ed25519 de paquetes ZIP IWFI v1.0

## Propósito

`iwfi/audit_package_signature.py` firma los bytes exactos de un ZIP de auditoría mediante Ed25519. La firma se conserva como sidecar JSON separado, evitando una dependencia circular (la firma no se inserta dentro del ZIP cuyo hash firma).

## Contenido firmado

El cuerpo firmado vincula:
- versión del formato de firma;
- algoritmo Ed25519;
- SHA-256 de los bytes exactos del ZIP;
- hash SHA-256 del manifiesto de inventario contenido en el ZIP;
- canonicalización `IWFI-JSON-C14N-1`;
- fingerprint SHA-256 de la clave pública.

El sidecar cumple `schemas/audit-package-signature-v1.0.schema.json`.

## Verificación

El verificador requiere la clave pública de confianza por separado. Comprueba fingerprint, firma Ed25519, hash del ZIP, manifiesto esperado, inventario y payloads. Una clave pública incluida dentro del sidecar no establece confianza.

La firma demuestra que la clave privada correspondiente firmó esos bytes; no prueba la verdad del contenido, identidad del proveedor, hora confiable, derechos de retención, ni que el firmante sea una entidad institucional. La clave privada debe permanecer fuera del repositorio y protegida por el operador. La clave pública debe distribuirse por un canal independiente y autenticado.

## Relación con checkpoints del journal

El repositorio ya implementa checkpoints Ed25519 para el journal local. Estos son un control separado: un checkpoint de journal no firma automáticamente un paquete ZIP. Este contrato cubre específicamente la autenticidad e integridad del artefacto ZIP transportable.

## Coste y límites

Usa la dependencia open source `cryptography` ya fijada en `requirements-test.txt`. No necesita servicios pagos, API, red, captura ni credenciales. Pruebas con claves sintéticas; coste externo 0 USD.
