-- =============================================================================
-- seed_community_profiles.sql
-- Simulación de la base de datos de una comunidad tech (estilo AI Tinkerers)
-- para un hackatón. TODOS los datos son ficticios: nombres, empresas, correos
-- (@example.invalid) y perfiles de LinkedIn. No representan personas reales.
--
-- Objetivo: alimentar a un agente "Perfilador" (que construye/enriquece
-- perfiles) y a un agente "Conector" (que empareja personas) por:
--   1) complementariedad: lo que A busca (looking_for) está en lo que B
--      ofrece (help_with);
--   2) problema/necesidad en común (mismo looking_for o mismo current_project);
--   3) intereses en común (columna interests).
--
-- Este script es idempotente: puede ejecutarse varias veces gracias a
-- ON CONFLICT (email) DO NOTHING.
--
-- -----------------------------------------------------------------------------
-- DISEÑO INTENCIONAL DE CRUCES (para que el Conector tenga material real)
-- -----------------------------------------------------------------------------
--
-- A) PAREJAS DE COMPLEMENTARIEDAD (>= 12; algunas mutuas, otras simples).
--    Contadas sobre los datos de este mismo archivo:
--      1.  Camila Restrepo (busca backend)         <-> Juan Pablo Zuluaga / Daniel
--          Zapata / Kevin Palacio (ofrecen backend)
--      2.  Mariana Cardona (busca frontend)        <-> Julián Vargas / Lorena
--          Castaño (ofrecen frontend)
--      3.  Santiago Vélez (busca diseno_ux)        <-> Sofía Escobar / Mariana
--          Cardona (ofrecen diseno_ux)
--      4.  Alejandro Montoya (busca producto)      <-> Daniela Betancur /
--          Sebastián Correa (ofrecen producto)
--      5.  Laura Martínez (RutaClara, busca datos_ml) <-> Manuela Sánchez /
--          Valentina Ospina (ofrecen datos_ml)
--      6.  Carlos Mario Toro (busca agentes_llm)   <-> Manuela Sánchez /
--          Juliana Pineda (ofrecen agentes_llm)
--      7.  PAR MUTUO: Sofía Escobar busca frontend y Julián Vargas lo ofrece;
--          Julián Vargas busca diseno_ux y Sofía Escobar lo ofrece.
--      8.  Mateo Uribe (busca frontend)            <-> Lorena Castaño (ofrece
--          frontend)
--      9.  Miguel Ángel Bermúdez (busca marketing) <-> Andrea Marín / Natalia
--          Arango (ofrecen marketing)
--      10. Nicolás Ramírez (busca mentoria)        <-> Carlos Mario Toro /
--          Ricardo Salazar / Tomás Herrera (ofrecen mentoria)
--      11. David Ochoa (busca cofundador)          <-> Juan Pablo Zuluaga
--          (ofrece cofundador)
--      12. Isabella Londoño (busca financiacion)   <-> Gloria Patricia Muñoz
--          (única persona que ofrece financiacion)
--      13. Felipe Giraldo (busca usuarios_pilotos) <-> Alejandro Montoya
--          (ofrece usuarios_pilotos)
--      14. Mateo Uribe (busca talento_empleo)      <-> Miguel Ángel Bermúdez
--          (ofrece talento_empleo)
--
-- B) HUECOS DEL ECOSISTEMA (tags muy buscados, casi nadie los ofrece; sirven
--    para que el Conector genere tareas al organizador, ej. "3 personas
--    buscan legal y no hay nadie que lo ofrezca"):
--      - legal:        3 personas lo buscan (Camila Restrepo, Paula Jaramillo,
--                       David Ochoa) / 0 personas lo ofrecen.
--      - financiacion: 7 personas lo buscan / solo 1 lo ofrece (Gloria
--                       Patricia Muñoz, la inversionista ángel).
--      - voz:          3 personas lo buscan (Camila Restrepo, Isabella
--                       Londoño, Paula Jaramillo) / 0 personas lo ofrecen
--                       como help_with (aunque sí hay interés/skills de voz
--                       en el ecosistema, p. ej. Juliana Pineda).
--
-- C) HOMÓNIMOS para probar desambiguación (mismo nombre, empresa/ciudad y
--    rol distintos):
--      - "Andrés Gómez": backend engineer en TechNova Labs (Medellín) vs.
--        diseñador UX en Pixelbrava (Bogotá).
--      - "Laura Martínez": frontend engineer en RutaClara (Medellín) vs.
--        especialista en marketing en una universidad privada (Envigado).
--
-- D) PERFILES MUY INCOMPLETOS (bio corta, sin looking_for, sin interests)
--    para forzar preguntas de check-in:
--      - Estefanía Vanegas, Catalina Rojas, Sara Isabel Trujillo.
--
-- E) PERFILES SOLO EN INGLÉS (languages = {'en'}) para probar el filtro de
--    idioma:
--      - James Walker, Sarah Mitchell.
--
-- F) Distribución de intereses: "agentes" aparece en 18/37 perfiles con
--    intereses (evento de agentes) y "voz" en 5/37, por ser un tema
--    recurrente pero más nicho.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS community;

CREATE TABLE IF NOT EXISTS community.profiles (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       text NOT NULL,
    email           text NOT NULL UNIQUE,
    company         text,
    role            text,
    seniority       text CHECK (seniority IN ('junior', 'mid', 'senior', 'founder', 'student')),
    city            text,
    languages       text[],
    bio             text,
    skills          text[],
    interests       text[],
    looking_for     text[],
    help_with       text[],
    current_project text,
    linkedin_url    text,
    registered_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE community.profiles IS
    'Simulación de la base de la comunidad organizadora (p. ej. API de AI Tinkerers). Datos ficticios.';

-- Vocabulario cerrado (documentado, no forzado por CHECK para mantener el
-- script simple; el Perfilador/Conector deben validar contra esta lista):
--   looking_for / help_with: backend, frontend, movil, diseno_ux, producto,
--     datos_ml, agentes_llm, voz, infra_devops, ventas_gtm, marketing,
--     financiacion, legal, mentoria, usuarios_pilotos, cofundador,
--     talento_empleo.
--   interests: agentes, voz, vision, educacion, salud, fintech, logistica,
--     eventos, gobierno, open_source, hardware_iot, creadores.

CREATE INDEX IF NOT EXISTS idx_profiles_skills      ON community.profiles USING GIN (skills);
CREATE INDEX IF NOT EXISTS idx_profiles_interests   ON community.profiles USING GIN (interests);
CREATE INDEX IF NOT EXISTS idx_profiles_looking_for ON community.profiles USING GIN (looking_for);
CREATE INDEX IF NOT EXISTS idx_profiles_help_with   ON community.profiles USING GIN (help_with);

-- =============================================================================
-- DATOS (40 perfiles ficticios)
-- =============================================================================

INSERT INTO community.profiles
    (full_name, email, company, role, seniority, city, languages, bio, skills,
     interests, looking_for, help_with, current_project, linkedin_url)
VALUES

-- 1
('Andrés Gómez', 'andres.gomez.tecnova@example.invalid', 'TechNova Labs (startup fintech, ficticia)',
 'Backend Engineer', 'mid', 'Medellín', ARRAY['es','en'],
 'Backend engineer con más de 5 años construyendo APIs para fintech en TechNova Labs. Sabe programar muy bien pero siente que le falta visión de producto, así que anda buscando a alguien que lo ayude a priorizar el roadmap. A cambio, ofrece su experiencia en backend e infraestructura a quien la necesite.',
 ARRAY['python','django','postgres','docker'],
 ARRAY['fintech','agentes','open_source'],
 ARRAY['producto','mentoria'],
 ARRAY['backend','infra_devops'],
 'API de pagos para pymes',
 'https://www.linkedin.com/in/andres-gomez-dev87'),

-- 2
('Andrés Gómez', 'andres.gomez.pixelbrava@example.invalid', 'Pixelbrava (agencia de eventos, ficticia)',
 'Diseñador UX', 'senior', 'Bogotá', ARRAY['es'],
 'Diseñador UX senior en Pixelbrava, una agencia de eventos en Bogotá. Ha rediseñado decenas de flujos de registro y quiere dar el salto a un equipo de producto más estable. Ofrece mentoría en diseño a quien esté empezando.',
 ARRAY['figma','research','prototyping'],
 ARRAY['eventos','creadores'],
 ARRAY['talento_empleo','frontend'],
 ARRAY['diseno_ux','mentoria'],
 'Rediseño de app de registro a eventos',
 'https://www.linkedin.com/in/andres-gomez-ux214'),

-- 3
('Laura Martínez', 'laura.martinez.rutaclara@example.invalid', 'RutaClara (startup de logística, ficticia)',
 'Frontend Engineer', 'mid', 'Medellín', ARRAY['es','en'],
 'Frontend engineer en RutaClara, una startup de logística, donde construye el dashboard de rutas en tiempo real. Le encantaría meter algo de machine learning para predecir tiempos de entrega, pero no sabe por dónde empezar. Ofrece ayuda con React y con diseño de interfaces a quien lo necesite.',
 ARRAY['react','typescript','tailwind'],
 ARRAY['logistica','agentes'],
 ARRAY['datos_ml','mentoria'],
 ARRAY['frontend','diseno_ux'],
 'Dashboard de rutas en tiempo real',
 'https://www.linkedin.com/in/laura-martinez-fe56'),

-- 4
('Laura Martínez', 'laura.martinez.marketing@example.invalid', 'Universidad privada (ficticia)',
 'Especialista en Marketing', 'senior', 'Envigado', ARRAY['es'],
 'Especialista en marketing digital para programas de posgrado en una universidad privada. Está armando la campaña de una maestría enfocada en IA y necesita entender mejor los datos de conversión. Ofrece su experiencia en marketing y en estrategias de ventas a quien la necesite.',
 ARRAY['seo','copywriting','analytics'],
 ARRAY['educacion','eventos'],
 ARRAY['datos_ml','ventas_gtm'],
 ARRAY['marketing','ventas_gtm'],
 'Campaña de admisiones para maestría en IA',
 'https://www.linkedin.com/in/laura-martinez-mkt99'),

-- 5
('Camila Restrepo', 'camila.restrepo@example.invalid', 'Nimbus Salud (startup de salud, ficticia)',
 'Fundadora / CEO', 'founder', 'Medellín', ARRAY['es','en'],
 'Fundadora de Nimbus Salud, una startup que construye un asistente de triage por IA para clínicas pequeñas. Está cerrando su ronda semilla y también necesita resolver temas legales de datos de salud y una interfaz de voz para pacientes mayores. Ofrece su experiencia en producto a otros fundadores en etapa temprana.',
 ARRAY['pitch','sql','notion'],
 ARRAY['salud','agentes','voz','gobierno'],
 ARRAY['financiacion','backend','legal','voz'],
 ARRAY['producto','mentoria'],
 'Asistente de triage por IA para clínicas',
 'https://www.linkedin.com/in/camila-restrepo-nimbus'),

-- 6
('Juan Pablo Zuluaga', 'juanpablo.zuluaga@example.invalid', 'Freelance / consultor independiente',
 'Backend Engineer (Freelance)', 'senior', 'Medellín', ARRAY['es','en'],
 'Backend engineer freelance con experiencia en Node y Kubernetes. Está construyendo un framework open source para orquestar agentes y busca early adopters que lo prueben en producción. Está abierto a sumarse como cofundador técnico si encuentra el proyecto correcto.',
 ARRAY['node.js','postgres','kubernetes'],
 ARRAY['agentes','open_source'],
 ARRAY['usuarios_pilotos'],
 ARRAY['backend','infra_devops','cofundador'],
 'Framework open source de orquestación de agentes',
 'https://www.linkedin.com/in/juanpablo-zuluaga-dev'),

-- 7
('Mariana Cardona', 'mariana.cardona@example.invalid', 'Vívelo (agencia de eventos, ficticia)',
 'Diseñadora UX', 'mid', 'Medellín', ARRAY['es'],
 'Diseñadora UX en Vívelo, una agencia de eventos, donde está prototipando una app de networking para asistentes a conferencias. Necesita un frontend developer para sacar el MVP y, si la idea funciona, le gustaría tener un socio que la acompañe. Ofrece diseño de producto a quien lo necesite.',
 ARRAY['figma','illustrator'],
 ARRAY['eventos','creadores','vision'],
 ARRAY['frontend','cofundador'],
 ARRAY['diseno_ux'],
 'App de networking para asistentes de conferencias',
 'https://www.linkedin.com/in/mariana-cardona-ux'),

-- 8
('Santiago Vélez', 'santiago.velez@example.invalid', 'RutaClara (startup de logística, ficticia)',
 'Desarrollador Móvil', 'mid', 'Medellín', ARRAY['es','en'],
 'Desarrollador móvil en RutaClara, construyendo la app de tracking para domiciliarios. Quiere mejorar la experiencia visual de la app y de paso entender mejor los datos de uso para tomar decisiones. Ofrece su experiencia en Kotlin y React Native.',
 ARRAY['kotlin','swift','react native'],
 ARRAY['logistica','hardware_iot'],
 ARRAY['diseno_ux','datos_ml'],
 ARRAY['movil'],
 'App de tracking de domiciliarios',
 'https://www.linkedin.com/in/santiago-velez-mobile'),

-- 9
('Valentina Ospina', 'valentina.ospina@example.invalid', 'Universidad pública (ficticia)',
 'Científica de Datos', 'mid', 'Bogotá', ARRAY['es','en'],
 'Científica de datos en una universidad pública, donde investiga modelos para predecir deserción estudiantil. Busca pilotos con colegios o universidades interesadas en probar su modelo, y también financiación para escalarlo. Ofrece apoyo en modelos de datos y machine learning.',
 ARRAY['python','pandas','sql','pytorch'],
 ARRAY['salud','vision'],
 ARRAY['usuarios_pilotos','financiacion'],
 ARRAY['datos_ml'],
 'Modelo de predicción de deserción estudiantil',
 'https://www.linkedin.com/in/valentina-ospina-data'),

-- 10
('Sebastián Correa', 'sebastian.correa@example.invalid', 'RutaClara (startup de logística, ficticia)',
 'Product Manager', 'senior', 'Medellín', ARRAY['es','en'],
 'Product manager en RutaClara, enfocado en el roadmap del cuarto trimestre. Cree que su producto necesita más inteligencia de datos y un mejor motor de ventas para crecer en otras ciudades. Ofrece su experiencia en gestión de producto y mentoría a fundadores primerizos.',
 ARRAY['notion','sql','pitch'],
 ARRAY['logistica','agentes'],
 ARRAY['datos_ml','ventas_gtm'],
 ARRAY['producto','mentoria'],
 'Rediseño del roadmap de producto para Q4',
 'https://www.linkedin.com/in/sebastian-correa-pm'),

-- 11
('Isabella Londoño', 'isabella.londono@example.invalid', 'Vozia (startup de voz, ficticia)',
 'Fundadora / CEO', 'founder', 'Medellín', ARRAY['es','en'],
 'Fundadora de Vozia, un asistente de voz para call centers en español. Está buscando financiación, un ingeniero de voz que se sume al equipo y, si aparece la persona correcta, un cofundador técnico. Ofrece ayuda con producto y con temas de contratación a otros founders.',
 ARRAY['whisper','python','pitch'],
 ARRAY['voz','agentes'],
 ARRAY['financiacion','voz','cofundador'],
 ARRAY['producto','talento_empleo'],
 'Asistente de voz para call centers en español',
 'https://www.linkedin.com/in/isabella-londono-vozia'),

-- 12
('Daniel Zapata', 'daniel.zapata@example.invalid', 'Bitforge (agencia digital, ficticia)',
 'Backend Developer', 'junior', 'Medellín', ARRAY['es'],
 'Backend developer junior en Bitforge, una agencia digital, migrando microservicios a Node. Le gustaría tener un mentor más senior y también está buscando su próximo reto laboral. Ofrece las manos para cualquier tarea de backend que necesiten.',
 ARRAY['node.js','express','mongodb'],
 ARRAY['open_source','agentes'],
 ARRAY['mentoria','talento_empleo'],
 ARRAY['backend'],
 'Migración de microservicios a Node',
 'https://www.linkedin.com/in/daniel-zapata-dev'),

-- 13
('Natalia Arango', 'natalia.arango@example.invalid', 'Vívelo (agencia de eventos, ficticia)',
 'Marketing', 'mid', 'Medellín', ARRAY['es'],
 'Encargada de marketing en Vívelo, armando la estrategia de contenido para el lanzamiento de una comunidad tech. Necesita ayuda de diseño y de un frontend developer para montar la landing page. Ofrece su experiencia en marketing y ventas a otros equipos.',
 ARRAY['copywriting','analytics','canva'],
 ARRAY['eventos','creadores'],
 ARRAY['diseno_ux','frontend'],
 ARRAY['marketing','ventas_gtm'],
 'Estrategia de contenido para lanzamiento de comunidad tech',
 'https://www.linkedin.com/in/natalia-arango-mkt'),

-- 14
('Felipe Giraldo', 'felipe.giraldo@example.invalid', 'Freelance / desarrollador independiente',
 'Desarrollador Móvil (Freelance)', 'mid', 'Cali', ARRAY['es','en'],
 'Desarrollador móvil freelance en Cali, construyendo una app para controlar sensores IoT en fincas cafeteras. Necesita un diseñador UX y usuarios piloto que prueben el producto en campo. Ofrece su experiencia con Flutter y apps móviles.',
 ARRAY['flutter','dart','firebase'],
 ARRAY['hardware_iot','creadores'],
 ARRAY['diseno_ux','usuarios_pilotos'],
 ARRAY['movil'],
 'App de control para dispositivos IoT en fincas cafeteras',
 'https://www.linkedin.com/in/felipe-giraldo-mobile'),

-- 15
('Mateo Uribe', 'mateo.uribe@example.invalid', 'CloudAndes (proveedor cloud, ficticia)',
 'Ingeniero de Infraestructura', 'senior', 'Medellín', ARRAY['es','en'],
 'Ingeniero de infraestructura senior en CloudAndes, un proveedor de servicios cloud. Ayuda a montar la plataforma de despliegue interna y está buscando un frontend developer para su panel de administración. También quiere hacer crecer su equipo con más talento.',
 ARRAY['terraform','aws','kubernetes','docker'],
 ARRAY['agentes','open_source'],
 ARRAY['frontend','talento_empleo'],
 ARRAY['infra_devops','backend'],
 'Plataforma interna de despliegue para startups',
 'https://www.linkedin.com/in/mateo-uribe-devops'),

-- 16
('Sofía Escobar', 'sofia.escobar@example.invalid', 'ModaLab (startup de moda, ficticia)',
 'Diseñadora UX', 'mid', 'Medellín', ARRAY['es'],
 'Diseñadora UX en ModaLab, construyendo el sistema de diseño para una app de moda circular. Necesita un frontend developer que implemente los componentes y un mentor que la ayude a crecer en su carrera. Ofrece diseño de producto y de interfaces.',
 ARRAY['figma','design systems'],
 ARRAY['creadores','vision'],
 ARRAY['frontend','mentoria'],
 ARRAY['diseno_ux','producto'],
 'Sistema de diseño para app de moda circular',
 'https://www.linkedin.com/in/sofia-escobar-ux'),

-- 17
('Nicolás Ramírez', 'nicolas.ramirez@example.invalid', 'Universidad privada (ficticia)',
 'Estudiante', 'student', 'Medellín', ARRAY['es','en'],
 'Estudiante de últimos semestres, trabajando en su tesis sobre agentes multimodales. Anda buscando un mentor en el tema y también su primera oportunidad laboral en el sector. Todavía no tiene mucho que ofrecer, pero tiene muchas ganas de aprender.',
 ARRAY['python','react','sql'],
 ARRAY['agentes','vision'],
 ARRAY['mentoria','talento_empleo'],
 ARRAY[]::text[],
 'Proyecto de tesis sobre agentes multimodales',
 'https://www.linkedin.com/in/nicolas-ramirez-student'),

-- 18
('Paula Jaramillo', 'paula.jaramillo@example.invalid', 'EduAgente (startup de educación, ficticia)',
 'Fundadora / CEO', 'founder', 'Medellín', ARRAY['es','en'],
 'Fundadora de EduAgente, un tutor de matemáticas con IA para colegios públicos. Necesita financiación, alguien que entienda de datos para medir el impacto, resolver temas legales de datos de menores y una interfaz de voz para los estudiantes más pequeños. Ofrece su experiencia en producto educativo a otros founders.',
 ARRAY['pitch','notion','sql'],
 ARRAY['educacion','agentes','voz'],
 ARRAY['financiacion','datos_ml','legal','voz'],
 ARRAY['producto','mentoria'],
 'Tutor de matemáticas con IA para colegios públicos',
 'https://www.linkedin.com/in/paula-jaramillo-eduagente'),

-- 19
('Alejandro Montoya', 'alejandro.montoya@example.invalid', 'Bitforge (agencia digital, ficticia)',
 'Ventas / GTM', 'senior', 'Medellín', ARRAY['es','en'],
 'Encargado de ventas en Bitforge, abriendo un canal B2B para pymes. Necesita mejorar el producto que está vendiendo y una estrategia de marketing más sólida. Ofrece su experiencia en ventas y en conseguir los primeros clientes piloto.',
 ARRAY['hubspot','negociación','pitch'],
 ARRAY['fintech','logistica'],
 ARRAY['producto','marketing'],
 ARRAY['ventas_gtm','usuarios_pilotos'],
 'Apertura de canal de ventas B2B para pymes',
 'https://www.linkedin.com/in/alejandro-montoya-sales'),

-- 20
('Manuela Sánchez', 'manuela.sanchez@example.invalid', 'Consultora de IA independiente (ficticia)',
 'Consultora en IA / Agentes LLM', 'senior', 'Medellín', ARRAY['es','en'],
 'Consultora independiente en IA, construyendo un framework de agentes para atención al cliente con LangGraph. Necesita un frontend developer para el panel de control y usuarios piloto que prueben el producto. Ofrece su experiencia en agentes LLM y en modelos de datos.',
 ARRAY['langgraph','python','langchain'],
 ARRAY['agentes','voz','open_source'],
 ARRAY['frontend','usuarios_pilotos'],
 ARRAY['agentes_llm','datos_ml'],
 'Framework de agentes para atención al cliente',
 'https://www.linkedin.com/in/manuela-sanchez-agents'),

-- 21
('Carlos Mario Toro', 'carlosmario.toro@example.invalid', 'Confiacol (banco regional, ficticio)',
 'Backend Engineer Senior', 'senior', 'Bogotá', ARRAY['es','en'],
 'Backend engineer senior en un banco regional, modernizando el core bancario. Le interesa meter agentes de IA en los procesos internos y quiere el ojo de un diseñador UX para la nueva interfaz. Ofrece su experiencia en backend y mentoría a devs más junior.',
 ARRAY['java','spring','postgres'],
 ARRAY['fintech','gobierno'],
 ARRAY['agentes_llm','diseno_ux'],
 ARRAY['backend','mentoria'],
 'Modernización de core bancario',
 'https://www.linkedin.com/in/carlosmario-toro-backend'),

-- 22
('Daniela Betancur', 'daniela.betancur@example.invalid', 'Nimbus Salud (startup de salud, ficticia)',
 'Product Manager', 'mid', 'Medellín', ARRAY['es'],
 'Product manager en Nimbus Salud, priorizando el roadmap de una historia clínica con IA. Necesita apoyo en ciencia de datos para medir resultados clínicos y financiación para el siguiente semestre. Ofrece su experiencia liderando producto.',
 ARRAY['notion','sql','figma'],
 ARRAY['salud','agentes'],
 ARRAY['datos_ml','financiacion'],
 ARRAY['producto'],
 'Priorización del roadmap de historia clínica con IA',
 'https://www.linkedin.com/in/daniela-betancur-pm'),

-- 23
('Julián Vargas', 'julian.vargas@example.invalid', 'ModaLab (startup de moda, ficticia)',
 'Frontend Developer', 'mid', 'Medellín', ARRAY['es','en'],
 'Frontend developer en ModaLab, rediseñando el checkout de la tienda online. Le gustaría trabajar más de cerca con un diseñador UX y tener un mentor que lo ayude a crecer técnicamente. Ofrece su experiencia con React y Next.js.',
 ARRAY['react','next.js','tailwind'],
 ARRAY['creadores','open_source'],
 ARRAY['diseno_ux','mentoria'],
 ARRAY['frontend'],
 'Rediseño del checkout de la tienda online',
 'https://www.linkedin.com/in/julian-vargas-frontend'),

-- 24 (perfil incompleto)
('Estefanía Vanegas', 'estefania.vanegas@example.invalid', 'Universidad pública (ficticia)',
 'Estudiante', 'student', 'Medellín', ARRAY['es'],
 'Estudiante de ingeniería, es su primera vez en un evento de tecnología.',
 ARRAY['python'],
 ARRAY[]::text[],
 ARRAY[]::text[],
 ARRAY[]::text[],
 NULL,
 'https://www.linkedin.com/in/estefania-vanegas'),

-- 25
('Ricardo Salazar', 'ricardo.salazar@example.invalid', 'Salazar & Asociados (firma legal, ficticia)',
 'Abogado', 'senior', 'Medellín', ARRAY['es'],
 'Abogado con su propia firma, especializado en contratos y propiedad intelectual. Está buscando clientes piloto en el ecosistema tech y también ampliar su equipo de trabajo. Ofrece mentoría a founders que necesiten entender mejor los temas legales de sus startups.',
 ARRAY['contratos','propiedad intelectual','notion'],
 ARRAY['gobierno','fintech'],
 ARRAY['usuarios_pilotos','talento_empleo'],
 ARRAY['mentoria'],
 NULL,
 'https://www.linkedin.com/in/ricardo-salazar-legal'),

-- 26
('Gloria Patricia Muñoz', 'gloria.munoz@example.invalid', 'Fondo de inversión ángel independiente (ficticio)',
 'Inversionista Ángel', 'senior', 'Medellín', ARRAY['es','en'],
 'Inversionista ángel, cerrando una ronda semilla para tres startups del ecosistema. Está buscando fundadores con tracción real y, ocasionalmente, un cofundador para alguna idea propia. Ofrece financiación y mentoría a equipos en etapa temprana.',
 ARRAY['finanzas','term sheets','pitch'],
 ARRAY['fintech','agentes','salud'],
 ARRAY['usuarios_pilotos','cofundador'],
 ARRAY['financiacion','mentoria'],
 'Ronda semilla para 3 startups del ecosistema',
 'https://www.linkedin.com/in/gloria-munoz-angel'),

-- 27
('Tomás Herrera', 'tomas.herrera@example.invalid', 'Grupo de investigación en IA, universidad pública (ficticio)',
 'Investigador', 'senior', 'Bogotá', ARRAY['es','en'],
 'Investigador en un grupo de IA de una universidad pública, trabajando en modelos de visión eficientes para dispositivos móviles. Busca financiación para seguir su investigación y empresas interesadas en probar sus modelos. Ofrece su experiencia en ciencia de datos y mentoría académica.',
 ARRAY['pytorch','papers','statistics'],
 ARRAY['vision','agentes','open_source'],
 ARRAY['financiacion','usuarios_pilotos'],
 ARRAY['datos_ml','mentoria'],
 'Investigación en modelos de visión eficientes para dispositivos móviles',
 'https://www.linkedin.com/in/tomas-herrera-research'),

-- 28
('Valeria Quintero', 'valeria.quintero@example.invalid', 'Freelance / desarrolladora independiente',
 'Desarrolladora Móvil (Freelance)', 'mid', 'Medellín', ARRAY['es','en'],
 'Desarrolladora móvil freelance, construyendo una app de comunidad para makers. Necesita un diseñador UX y un backend developer que la apoye con la parte de servidor. Ofrece su experiencia con React Native y Firebase.',
 ARRAY['react native','typescript','firebase'],
 ARRAY['hardware_iot','creadores'],
 ARRAY['diseno_ux','backend'],
 ARRAY['movil'],
 'App de comunidad para makers',
 'https://www.linkedin.com/in/valeria-quintero-mobile'),

-- 29
('Andrea Marín', 'andrea.marin@example.invalid', 'ModaLab (startup de moda, ficticia)',
 'Marketing Junior', 'junior', 'Medellín', ARRAY['es'],
 'Encargada de marketing junior en ModaLab, lanzando una campaña en redes para una colección cápsula. Le gustaría aprender más de diseño y tener un mentor en el área de marketing. Ofrece su experiencia con redes sociales y contenido.',
 ARRAY['canva','redes sociales','copywriting'],
 ARRAY['creadores','eventos'],
 ARRAY['diseno_ux','mentoria'],
 ARRAY['marketing'],
 'Campaña de lanzamiento en redes para colección cápsula',
 'https://www.linkedin.com/in/andrea-marin-mkt'),

-- 30
('Kevin Palacio', 'kevin.palacio@example.invalid', 'Freelance / bootcamp de programación',
 'Backend Developer Junior', 'junior', 'Medellín', ARRAY['es'],
 'Backend developer junior, construyendo una API para un bot de reservas por WhatsApp. Está buscando un mentor más senior y su primera oportunidad laboral formal en tecnología. Ofrece las ganas de aprender y ayuda básica con Python y Flask.',
 ARRAY['python','flask','sql'],
 ARRAY['agentes','open_source'],
 ARRAY['mentoria','talento_empleo'],
 ARRAY['backend'],
 'API para bot de WhatsApp de reservas',
 'https://www.linkedin.com/in/kevin-palacio-backend'),

-- 31
('Lorena Castaño', 'lorena.castano@example.invalid', 'Bitforge (agencia digital, ficticia)',
 'Frontend Developer', 'mid', 'Cali', ARRAY['es','en'],
 'Frontend developer en Bitforge, en Cali, construyendo un portal de autoservicio para clientes. Le gustaría tener más visión de producto y conseguir un backend developer para un proyecto propio que tiene en mente. Ofrece su experiencia con Vue y diseño de interfaces.',
 ARRAY['vue','javascript','css'],
 ARRAY['creadores','open_source'],
 ARRAY['producto','backend'],
 ARRAY['frontend','diseno_ux'],
 'Portal de autoservicio para clientes',
 'https://www.linkedin.com/in/lorena-castano-frontend'),

-- 32
('David Ochoa', 'david.ochoa@example.invalid', 'AgroSensa (startup agtech, ficticia)',
 'Fundador / CEO', 'founder', 'Envigado', ARRAY['es','en'],
 'Fundador de AgroSensa, sensores de humedad para pequeños caficultores. Está buscando un cofundador técnico, financiación, infraestructura en la nube y resolver temas legales para formalizar la empresa. Ofrece su conocimiento de producto y del sector agro.',
 ARRAY['arduino','python','pitch'],
 ARRAY['hardware_iot','logistica'],
 ARRAY['cofundador','financiacion','legal','infra_devops'],
 ARRAY['producto'],
 'Sensores de humedad para pequeños caficultores',
 'https://www.linkedin.com/in/david-ochoa-agrosensa'),

-- 33
('Juliana Pineda', 'juliana.pineda@example.invalid', 'Freelance / investigadora en voz',
 'Investigadora en Voz', 'mid', 'Medellín', ARRAY['es','en'],
 'Investigadora independiente en tecnología de voz, construyendo un modelo para detectar emociones en llamadas de call center. Necesita usuarios piloto y a alguien más metido en agentes LLM para integrarlo en un producto real. Ofrece su experiencia en modelos de datos y procesamiento de audio.',
 ARRAY['whisper','python','pytorch'],
 ARRAY['voz','agentes','salud'],
 ARRAY['agentes_llm','usuarios_pilotos'],
 ARRAY['datos_ml','agentes_llm'],
 'Modelo de detección de emociones por voz para call centers',
 'https://www.linkedin.com/in/juliana-pineda-voz'),

-- 34
('Esteban Duque', 'esteban.duque@example.invalid', 'CloudAndes (proveedor cloud, ficticia)',
 'Ingeniero DevOps', 'mid', 'Medellín', ARRAY['es','en'],
 'Ingeniero de infraestructura en CloudAndes, armando un pipeline de CI/CD multi-cloud. Le gustaría tener más cercanía con el equipo de producto y con un frontend developer para las herramientas internas. Ofrece su experiencia en DevOps.',
 ARRAY['docker','ci/cd','aws'],
 ARRAY['open_source','hardware_iot'],
 ARRAY['frontend','producto'],
 ARRAY['infra_devops'],
 'Pipeline de CI/CD para despliegues multi-cloud',
 'https://www.linkedin.com/in/esteban-duque-devops'),

-- 35 (perfil incompleto)
('Catalina Rojas', 'catalina.rojas@example.invalid', 'Universidad privada (ficticia)',
 'Estudiante', 'student', 'Medellín', ARRAY['es'],
 'Estudiante de diseño, viene explorando el ecosistema de IA por primera vez.',
 ARRAY['figma'],
 ARRAY[]::text[],
 ARRAY[]::text[],
 ARRAY[]::text[],
 NULL,
 'https://www.linkedin.com/in/catalina-rojas'),

-- 36
('Miguel Ángel Bermúdez', 'miguelangel.bermudez@example.invalid', 'RutaClara (startup de logística, ficticia)',
 'Ventas / GTM', 'senior', 'Medellín', ARRAY['es','en','pt'],
 'Encargado de ventas en RutaClara, expandiendo la operación comercial a Bogotá y Cali. Necesita mejorar el producto y una estrategia de marketing más agresiva para la expansión. Ofrece su experiencia en ventas y en conseguir talento comercial.',
 ARRAY['negociación','crm','pitch'],
 ARRAY['logistica','fintech'],
 ARRAY['marketing','producto'],
 ARRAY['ventas_gtm','talento_empleo'],
 'Expansión comercial a Bogotá y Cali',
 'https://www.linkedin.com/in/miguelangel-bermudez-sales'),

-- 37
('Diego Fernando Cano', 'diego.cano@example.invalid', 'Bitforge (agencia digital, ficticia)',
 'Product Manager', 'senior', 'Bogotá', ARRAY['es','en'],
 'Product manager en Bitforge, trabajando en un producto interno de automatización con agentes para el sector público. Necesita apoyo en ciencia de datos y en diseño de la interfaz. Ofrece su experiencia liderando producto y mentoría a otros PMs.',
 ARRAY['notion','sql','figma'],
 ARRAY['agentes','gobierno'],
 ARRAY['datos_ml','diseno_ux'],
 ARRAY['producto','mentoria'],
 'Producto interno de automatización con agentes para el sector público',
 'https://www.linkedin.com/in/diego-cano-producto'),

-- 38 (perfil incompleto)
('Sara Isabel Trujillo', 'sara.trujillo@example.invalid', 'Freelance / diseñadora independiente',
 'Diseñadora UX (Freelance)', 'junior', 'Medellín', ARRAY['es'],
 'Diseñadora freelance, llegó por una amiga y todavía no tiene muy claro qué busca en el evento.',
 ARRAY['figma'],
 ARRAY[]::text[],
 ARRAY[]::text[],
 ARRAY['diseno_ux'],
 NULL,
 'https://www.linkedin.com/in/sara-trujillo-ux'),

-- 39 (solo inglés)
('James Walker', 'james.walker@example.invalid', 'Startup de fintech remota (EE. UU., ficticia)',
 'Backend Engineer', 'mid', 'Medellín', ARRAY['en'],
 'Backend engineer building payment infrastructure for LATAM remittances at a remote US-based fintech startup. Recently moved to Medellín and is looking for a technical cofounder and pilot users for a side project. Happy to help with backend and infrastructure work in the meantime.',
 ARRAY['go','postgres','aws'],
 ARRAY['fintech','open_source'],
 ARRAY['cofundador','usuarios_pilotos'],
 ARRAY['backend','infra_devops'],
 'Payment infrastructure for LATAM remittances',
 'https://www.linkedin.com/in/james-walker-backend'),

-- 40 (solo inglés)
('Sarah Mitchell', 'sarah.mitchell@example.invalid', 'Consultora de crecimiento (ficticia)',
 'Growth / Producto', 'senior', 'Medellín', ARRAY['en'],
 'Growth and product consultant helping AI-agent startups expand into Latin America. Looking for data science support and talent to build out a local team. Offers marketing and go-to-market help to early-stage founders.',
 ARRAY['analytics','sql','notion'],
 ARRAY['agentes','creadores'],
 ARRAY['datos_ml','talento_empleo'],
 ARRAY['marketing','ventas_gtm'],
 'Growth playbook for AI-agent startups expanding to LATAM',
 'https://www.linkedin.com/in/sarah-mitchell-growth')

ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- CONSULTAS DE VERIFICACIÓN (ejecútalas después de cargar el seed)
-- =============================================================================

-- 1) Conteo total de perfiles cargados.
SELECT count(*) AS total_perfiles FROM community.profiles;

-- 2) Tags más buscados (looking_for) vs. más ofrecidos (help_with), para que
--    el Conector detecte huecos como legal, financiacion o voz.
SELECT
    coalesce(b.tag, o.tag)          AS tag,
    coalesce(b.buscan, 0)::int      AS personas_que_buscan,
    coalesce(o.ofrecen, 0)::int     AS personas_que_ofrecen
FROM
    (SELECT unnest(looking_for) AS tag, count(*) AS buscan
     FROM community.profiles GROUP BY 1) b
FULL OUTER JOIN
    (SELECT unnest(help_with) AS tag, count(*) AS ofrecen
     FROM community.profiles GROUP BY 1) o
    ON b.tag = o.tag
ORDER BY personas_que_buscan DESC, personas_que_ofrecen ASC;

-- 3) Nombres duplicados (homónimos) que requieren desambiguación, con sus
--    correos y empresas para distinguirlos.
SELECT full_name, count(*) AS apariciones, array_agg(email ORDER BY email) AS emails
FROM community.profiles
GROUP BY full_name
HAVING count(*) > 1
ORDER BY full_name;
