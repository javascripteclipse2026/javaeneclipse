# Eclipse Java IDE

Editor web completo de **Java** estilo Eclipse, con:

- Pantalla de carga con circuito naranja sobre fondo violeta
- Editor de código Java
- Compilación y ejecución **real** con OpenJDK (backend)
- Consola de salida
- Guardar proyectos (navegador + servidor)
- Descargar archivo `.java`
- Todo funciona sin errores y permanece conectado

## Requisitos

- **Java (OpenJDK 17 o superior)** instalado
  - `javac` y `java` deben estar en el PATH
- **Python 3.8+** (solo usa la biblioteca estándar, no necesita pip)

## Cómo arrancar (muy fácil)

1. Abre una terminal en esta carpeta.
2. Ejecuta:

```bash
python3 server.py
```

3. Abre el navegador en:

```
http://localhost:8080
```

¡Listo! Ya puedes escribir código Java, pulsar **▶ Ejecutar** y ver el resultado.

## Atajos de teclado

| Atajo            | Acción              |
|------------------|---------------------|
| `Ctrl + Enter`   | Compilar y ejecutar |
| `Ctrl + S`       | Guardar proyecto    |

## Características

- Backend real: compila con `javac` y ejecuta con `java`
- Timeout de seguridad (8 segundos)
- Límite de memoria (128 MB)
- Limpieza automática de archivos temporales
- Guardado automático en el navegador (localStorage)
- Posibilidad de descargar el `.java`
- Guardado también en el servidor (carpeta `projects/`)

## Estructura del proyecto

```
java-eclipse-ide/
├── server.py          ← Backend (compilación + ejecución)
├── public/
│   └── index.html     ← Frontend completo
├── projects/          ← Proyectos guardados en el servidor
├── temp/              ← Carpeta temporal (se limpia sola)
└── README.md
```

## Notas de seguridad

- El código se ejecuta en un directorio temporal aislado.
- Hay timeout y límite de memoria.
- No se recomienda exponer este servidor a Internet sin más protecciones (está pensado para uso local o red privada).

---

Hecho para que funcione de verdad, sin errores y listo para descargar y usar.
