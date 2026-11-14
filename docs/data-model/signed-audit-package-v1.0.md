# Firma detached Ed25519 de paquetes ZIP IWFI v1.0

## Contrato

`iwfi/signed_audit_package.py` firma los bytes exactos del ZIP mediante Ed25519. La firma se entrega como envelope JSON separado; no se modifica el ZIP firmado.

El envelope fija:
- tipo de artefacto y media type;
- tamaño exacto y SHA-256 del ZIP;
- versión de canonicalización y algoritmo;
- hora declarada de emisión;
- fingerprint SHA-256 de la clave pública;
- firma Ed25519 del cuerpo canonicalizado.

## Verificación

El verificador exige una clave pública confiable proporcionada por separado. No confía en una clave embebida en el envelope. Comprueba la firma, fingerprint, tamaño y hash del ZIP. La integridad interna del ZIP debe comprobarse además con `verify_audit_package_zip`; ambas verificaciones tienen propósitos distintos.

## Custodia y límites

- La clave privada nunca se guarda en el repositorio ni la genera esta API de firma.
- El operador debe protegerla fuera del sistema que almacena el paquete.
- El envelope y la clave pública/fingerprint deben distribuirse o anclarse por un canal independiente.
- `issued_at_utc` es una hora declarada, no un trusted timestamp.
- Ed25519 demuestra control de la clave firmante, no veracidad del contenido, identidad legal del firmante, derechos de retención ni causalidad económica.
- Rotación, revocación, certificados, timestamping confiable y gestión hardware de claves quedan fuera de esta versión.

## Coste

Usa `cryptography` ya fijada en `requirements-test.txt`; no agrega servicios ni dependencias externas. Pruebas sintéticas, coste externo 0 USD.
