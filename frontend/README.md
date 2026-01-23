# Semáforo de Gestión - Frontend

Dashboard de métricas para Grupo Padova.

## Tecnologías
- React 18
- Vite
- Axios

## Desarrollo Local

```bash
# Instalar dependencias
npm install

# Ejecutar en modo desarrollo
npm run dev
```

## Variables de Entorno

Crear archivo `.env` basado en `.env.example`:

```env
VITE_API_URL=http://localhost:8000/api
```

## Despliegue en Vercel

### Opción 1: CLI

```bash
# Instalar Vercel CLI
npm i -g vercel

# Desplegar
vercel

# Producción
vercel --prod
```

### Opción 2: GitHub Integration

1. Crear cuenta en [Vercel](https://vercel.com)
2. Importar repositorio de GitHub
3. Configurar variable de entorno:
   - `VITE_API_URL=https://tu-backend.railway.app/api`
4. Desplegar

## Build

```bash
npm run build
```

Los archivos estáticos se generarán en la carpeta `dist/`.
