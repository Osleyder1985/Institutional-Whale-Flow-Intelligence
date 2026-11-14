# Exportación ZIP reproducible de paquetes de auditoría IWFI v1.0

## Alcance

`iwfi/audit_package_zip.py` convierte un manifiesto de inventario ya verificado y su mapa exacto de bytes en un ZIP reproducible. Incluye `audit-package-manifest.json` y todos los artefactos inventariados.

## Determinismo

- Entradas ordenadas por ruta.
- Timestamp ZIP fijo en el mínimo representable (1980-01-01 00:00:00).
- Sin comentarios ni campos extra variables.
- Permisos POSIX de archivo regular normalizados.
- `ZIP_STORED` (sin compresión) para evitar variaciones por versión de zlib/deflate entre plataformas.
- Manifiesto serializado con `IWFI-JSON-C14N-1`.

La garantía se limita a las mismas entradas exactas, misma versión de Python/zipfile y mismo contrato. Las pruebas exigen igualdad byte a byte en ejecuciones repetidas. No se promete identidad universal entre todas las implementaciones futuras del formato ZIP.

## Verificación offline

`verify_audit_package_zip` opera directamente sobre bytes:
- no extrae archivos ni escribe en el filesystem;
- rechaza entradas duplicadas, directorios, cifrado, compresión no soportada, timestamps variables, enlaces simbólicos y rutas inseguras;
- valida la canonicalización del manifiesto;
- exige igualdad exacta entre el inventario y los archivos del ZIP;
- verifica tamaños y SHA-256 mediante el verificador de inventario;
- valida el hash de reconstrucción esperado que entrega el verificador externo.

La verificación no prueba autoría del proveedor ni verdad económica. La autenticidad del paquete requiere firma detached Ed25519 y una clave pública obtenida por un canal independiente; no debe confundirse con SHA-256. El módulo de checkpoints Ed25519 del journal ya existente es un control distinto y no firma automáticamente este ZIP.

## Derechos de retención

El exportador solo acepta bytes ya incluidos en el inventario autorizado. No decide derechos ni amplía permisos de retención o redistribución. Si una evidencia solo admite metadata/hash, no se debe incluir su payload ni etiquetar el paquete como reconstrucción completa.

## Coste y límites

Biblioteca estándar de Python; no requiere servicio, API, red, captura ni credenciales. Fixtures sintéticos; coste externo 0 USD. El paquete no cifra datos y no sustituye controles de acceso.
