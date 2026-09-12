# db/

Seed SQL para Postgres (Supabase) que simula la base de datos de una
comunidad tech tipo AI Tinkerers, con 40 perfiles ficticios de asistentes a
un evento. Sirve para probar un agente "Perfilador" (construye perfiles) y
un agente "Conector" (empareja personas por complementariedad, necesidad en
común e intereses en común).

## Cargarlo

```sh
psql "$SUPABASE_DB_URL" -f db/seed_community_profiles.sql
```

El script crea el esquema `community` y la tabla `community.profiles` si no
existen, e inserta los perfiles con `ON CONFLICT (email) DO NOTHING`, así que
es seguro volver a ejecutarlo. Al final imprime 3 consultas de verificación
(conteo total, tags más buscados vs. más ofrecidos, y homónimos).

Todos los nombres, empresas, correos (`@example.invalid`) y perfiles de
LinkedIn son **ficticios**; no representan personas ni organizaciones reales.
