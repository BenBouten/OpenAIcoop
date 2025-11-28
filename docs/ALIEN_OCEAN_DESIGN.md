# Alien Ocean Design

## Visie
- Evolutie-simulator
- Newtoniaanse fysica (position, velocity, forces, mass, drag, energy)
- Setting: Alien Ocean met dieptelagen (sunlit / twilight / dark / abyss)
- Zijaanzicht (denk aan *Ecco the Dolphin*): zwaartekracht, drijfvermogen en druk nemen toe met diepte

## Kernsystemen
1. **DNA & traits** – genetische representatie van fysieke en gedragskenmerken.
2. **Lifeforms / creatures** – entiteiten die eigenschappen erven, muteren en evolueren.
3. **World / biomes** – generieke wereldlaag die later wordt uitgebreid naar oceaan-ecosystemen.
4. **Physics layer** – 2D newtoniaanse simulatie in water met krachten (thrust, drag, buoyancy) en stromingen.
5. **Energy & fitness** – energiemodel gekoppeld aan fysica voor verbruik en efficiëntie.

### Neuraal gedrag
- Elke lifeform krijgt een vaste feedforward-controller (10 inputs → 12 verborgen neuronen → 7 outputs) waarvan alle gewichten als vlakke floatlijst in het DNA zitten.【F:evolution/entities/neural_controller.py†L1-L82】
- Inputs omvatten lokale voedsel-densiteit voorwaarts/links/rechts, genormaliseerde diepte, energieratio, buurtdichtheid, verticale snelheid, actuele snelheid, ruis en een simpele drijfvermogen-bias.【F:evolution/entities/ai.py†L84-L110】
- Outputs gaan uitsluitend naar actuatoren: staart- en fin-thrust, verticale thrust, bijtintentie en bioluminescentie-intensiteit/patroon; de waardes worden rechtstreeks gebruikt door de physicslaag en sturen geen posities of doelen aan.【F:evolution/entities/ai.py†L40-L71】【F:evolution/entities/ai.py†L112-L142】
- Tijdens reproductie worden de gewichten gemiddeld tussen ouders en vervolgens met kleine Gaussische noise gemuteerd zodat gedrag kan evolueren zonder nieuwe logica te coderen.【F:evolution/entities/reproduction.py†L55-L98】【F:evolution/entities/reproduction.py†L210-L243】

## Modulair lichaamssysteem

Het nieuwe lijf wordt niet langer beschreven door vlakke `width/height`-velden maar door een modulair “lego” systeem:

### BodyGraph
- `BodyGraph` is een boom van `BodyNode`-objecten waarin elk knooppunt een `BodyModule` bevat en verwijst naar zijn ouder + attachment-slot. Hierdoor kunnen we vinnen, sensoren en thrusters exact positioneren en later terugvinden voor AI/physics-logica.【F:evolution/body/body_graph.py†L12-L93】
- Elke module levert tijdens aggregatie zijn massa, volumes, doorsnede-oppervlakken en krachten. `aggregate_physics_stats()` loopt over alle modules, combineert thrust/grip/power en onthoudt het totale drag-oppervlak zodat we downstream automatisch hydrodynamische parameters krijgen.【F:evolution/body/body_graph.py†L34-L93】
- Attachment-regels worden enforced bij `add_module()`. Het systeem controleert of het opgegeven `AttachmentPoint` de module accepteert (type, materiaal, max massa) en reset de cached physics zodat iedere wijziging opnieuw wordt doorgerekend.【F:evolution/body/body_graph.py†L95-L165】
- Traversal helpers (`iter_modules`, `children_of`, depth-first) maken het eenvoudig om bijvoorbeeld alleen sensorclusters of propulsion chains te inspecteren voor AI en mutations.【F:evolution/body/body_graph.py†L167-L205】

### Modules & attachment-primitieven
- Basisklassen (`CoreModule`, `HeadModule`, `LimbModule`, `PropulsionModule`, `SensoryModule`) delen `ModuleStats` (massa, energiekost, integriteit, power output) zodat physicsberekeningen altijd consistente velden zien.【F:evolution/body/modules.py†L1-L90】
- Elke concrete module brengt eigen sockets mee. De standaard `TrunkCore` heeft vijf attachment-punten met Joint-metadata (hinge, ball, muscle) inclusief massalimieten en toegestane materialen, waardoor evolutie kan experimenteren met asymmetrische vinconfiguraties of dorsal sensor arrays.【F:evolution/body/modules.py†L92-L169】
- Andere presets zoals `CephalonHead`, `HydroFin`, `TailThruster` en `SensorPod` vullen het basisschema: vinnen leveren thrust+grip, thrusters leveren burst power + sensor sockets, en sensoren declareren spectrum/range. Deze gegevens bepalen direct energieverbruik, locomotietype en sensorvoordelen.【F:evolution/body/modules.py†L170-L260】
- `AttachmentPoint` en `Joint` beschrijven precies hoe modules samenkomen (fix/hinge/ball/muscle, swing/twist-limieten, torque) en voeren runtime checks uit voor massa/materiaal-compatibiliteit voordat een module wordt gekoppeld.【F:evolution/body/attachment.py†L1-L58】【F:evolution/body/attachment.py†L61-L88】

### DNA ↔ graph
- `evolution.dna.factory.build_body_graph()` leest een `Genome` en instantiateert modules via `DEFAULT_MODULE_FACTORIES`. Elk `ModuleGene` bepaalt type, parameters en parent-slot; daarna valideert het systeem massalimiet en `nerve_capacity` om overbouwde creaties te voorkomen.【F:evolution/dna/factory.py†L1-L113】【F:evolution/dna/factory.py†L116-L160】
- `serialize_body_graph()` exporteert het resultaat terug naar een `Genome`, inclusief automatisch opgeschaalde constraints als de huidige graph zwaarder of zenuw-intensiever is dan de default. Hierdoor kunnen mutaties veilig heen en weer tussen DNA en runtime body graphs.【F:evolution/dna/factory.py†L163-L206】
- Tests bewaken de volledige round-trip, massa/nerve-validatie en de verwachte module-structuur. Hiermee houden we regressies in de assemblage tegen terwijl we nieuwe moduletypes toevoegen.【F:tests/test_dna_factory.py†L1-L40】

### DNA blueprints & populatie-integratie
- `generate_modular_blueprint()` bouwt voor elk dieettype een klein maar valide moduleplan met kern, thruster, vinnen en sensor-suites; randomness bepaalt extra sensoren maar het resultaat blijft binnen `GenomeConstraints`, waardoor elke DNA-profiel op zijn minst een bruikbaar lichaamsplan bezit.【F:evolution/dna/blueprints.py†L1-L94】
- Zowel het bootstrap-proces als reproductie haken hierin: `generate_dna_profiles()` vult alle catalogusprofielen met een blueprint op basis van hun dieet, terwijl `_mix_parent_genome()` bij het ontbreken van ouder-genomen automatisch een blueprint genereert. Hierdoor zijn newborns en seeds altijd compatibel met het modulaire lichaamssysteem.【F:evolution/simulation/bootstrap.py†L62-L135】【F:evolution/entities/reproduction.py†L70-L120】
- Dedicated tests bouwen een BodyGraph uit de blueprint en verifiëren zowel de structurele geldigheid als dieetvariatie in sensor-spectrums, zodat regressies in de generator direct zichtbaar worden.【F:tests/test_dna_blueprints.py†L1-L26】
- De startpopulatie komt uit een kleine set neutrale baseforms (common ancestor + optionele varianten) met symmetrische thruster + vinnen rond het massacentrum. Elk basisprofiel bevat een klein brein met willekeurig gewichtjes en wordt bij het klonen licht gemuteerd in lichaam en controller zodat alle diversiteit uit evolutie ontstaat, niet uit vaste rollen.【F:evolution/simulation/base_population.py†L9-L138】
- Het aantal basisvormen en de populatiegrootte zijn configureerbaar via `INITIAL_BASEFORM_COUNT` en `N_LIFEFORMS` in de centrale settings/CLI/YAML, waardoor de seeding in één plek af te stemmen is.【F:evolution/config/settings.py†L41-L118】【F:configs/default.yaml†L1-L11】
- Spawning plaatst deze clones bewust rond meerdere voedselpatches op verschillende dieptes in plaats van uniform random, waardoor vroege gedragsdiversiteit meteen gekoppeld wordt aan resource hotspots.【F:evolution/simulation/bootstrap.py†L239-L323】

### PhysicsBody bridge
- `BodyGraph.aggregate_physics_stats()` levert een `PhysicsAggregation` met massa, volume, drag-oppervlak, totale thrust, grip en power. `build_physics_body()` vertaalt die naar een compacte `PhysicsBody` met dichtheid, drag-coëfficiënt en maximale voortstuwing die direct in de Newtoniaanse ocean-simulator kan worden gebruikt.【F:evolution/body/body_graph.py†L34-L93】【F:evolution/physics/physics_body.py†L1-L53】
- De resulterende `PhysicsBody` kan acceleratie berekenen op basis van thrust-effort en geeft hydrodynamische parameters terug aan movement/AI zodat locomotie-archetypen automatisch uit de modulecombinaties rollen.【F:evolution/physics/physics_body.py†L7-L40】

## UI & statistieken
- Tijdens spawning bouwt `Lifeform` zijn `BodyGraph` en `PhysicsBody`, waarna de resulterende waarden (modulecount, massa, drag, thrust, energie-upkeep, sensor-suite) worden gekopieerd naar publieke attributen. Deze stats voeden AI, energie- en locomotierekeningen maar worden nu ook geëxposeerd voor visualisatie.【F:evolution/entities/lifeform.py†L29-L142】
- De `LifeformInspector` toont een sectie “Modulaire anatomie” waarin moduletypes, sensorbanden, drag/thrust en onderhoudskosten worden weergegeven met tooltips, zodat spelers de impact van het modulaire lichaam direct in de UI lezen.【F:evolution/rendering/lifeform_inspector.py†L280-L360】
- Populatiestatistieken aggregeren dezelfde physics-data: `systems.stats` bundelt gemiddelde modulecounts, drag, thrust en energie-upkeep terwijl `stats_window` de waarden rendert in de HUD. Zo blijft de globale simulatiegezondheid zichtbaar tijdens lange runs.【F:evolution/systems/stats.py†L1-L52】【F:evolution/rendering/stats_window.py†L1-L80】

### Newtonian Ocean Physics
- Meerlaags model (sunlit / twilight / midnight / abyss) met dichtheid, temperatuur en lichtverval per laag.
- `OceanPhysics` voorziet elke lifeform van fluid properties (druk, licht, stroming, dichtheid) en integreert versnellingen → snelheid → positie.
- Lifeforms hebben massa, volume, drag-coefficient en voortstuwingsefficiëntie op basis van hun morfologie.
- Licht & druk hebben directe invloed op energie / gezondheid zodat dieptekeuzes voelbaar zijn.
- Locomotie wordt volledig oceaan-gebaseerd: geen landtrillingen meer maar vinnen, jetblasts, drift, grijptentakels en elektromagnetische zintuigen.

### Locomotie archetypes
Ocean-evolution kent zes automatisch afgeleide strategieën uit DNA/morfologie:

1. **Fin-based swimmers** – Oscillerende vinnen leveren efficiënte thrust en hoge topsnelheid.
2. **Jet propulsion** – Mantelcompressies geven dure snelheidsbursts voor Newton/Energie fitness-tests.
3. **Drift feeders** – Sensor-zware zwevers laten zich door stromingen voeren en filteren planktonwolken.
4. **Benthic crawlers** – Gemuteerde pootjes kruipen veilig over de bodem met hoge grip op rotsen.
5. **Tentacle locomotion** – Langzame tentakelgangers met grip physics voor interactie met mineralen.
6. **Electromagnetic sensing beasts** – Diepzee stalkers met geur+elektrische “signal cones” i.p.v. zicht.

Elke strategie bepaalt thrust-efficiëntie, energieverbruik, grip, sensorbonus, drift-voorkeur en dieptebias zodat movement- en AI-systemen automatisch op de nieuwe werkelijkheid inspelen.

### Carrion & voedselketen
- Gestorven dieren spawnen een `SinkingCarcass` die langzaam naar de bodem zakt en vervalt.
- Carcassen zijn voedsel voor carnivoren/omnivoren; AI deelt locaties in geheugen/groep en plantblokkerende logica is aangepast.
- De oceaan bevat zo een doorlopend nutriënten-cyclus: dode wezens worden energiebron voor volgende generaties.

## Roadmap
- **Fase A**: bestaande code opschonen en physics-fundament opzetten (componenten voor massa, krachten, energie).
- **Fase B**: creatures koppelen aan physics en energy/fitness-systemen voor evolutie-feedback.
- **Fase C**: wereld ombouwen naar oceaan-lagen (sunlit/twilight/dark/abyss) en water-specifieke traits toevoegen.

## Integratieplan richting productie & POC

Onderstaand stappenplan integreert het modulaire lichaamssysteem in de productiestack en levert een eerste speelbare sideways-ocean POC.

### 1. Stabiliseer en exposeer het modulaire fundament (Week 1)
1. **Publiceer API-contract** – documenteer `BodyGraph`, modulecatalogus en `PhysicsBody` als “supported” zodat gameplayteams weten welke velden stable zijn.
2. **Validatiehooks toevoegen** – breid `build_body_graph()` uit met hard errors voor ontbrekende modules, dubbele sockets en invalid attachments zodat productiespawn nooit een invalide graph kan maken.
3. **Snapshot-tests** – voeg regressietests toe die het volledige module → physics-resultaat vergelijken met opgeslagen fixtures voor drie referentiewezens (drifter, crawler, predatory swimmer). Dit beschermt de API tijdens verdere integratie.

### 2. Vervang legacy DNA in productie-spawn (Week 2)
1. **`LifeformFactory` herschrijven** – laat `spawn_lifeforms()` uitsluitend `BodyGraph`-gedreven stats aanmaken (massa, drag, thrust) en verwijder de oude `width/height` profielen.
2. **Reproductie rework** – update `reproduction.create_offspring_profile()` zodat mutaties modules toevoegen/verwijderen i.p.v. vlakke numerieke tweaks. Introduceer een beperkte set mutators (swap fin, upsize thruster, attach sensorpod) zodat evolutie de nieuwe modules effectief gebruikt.
3. **Migration script** – schrijf een eenmalige converter die bestaande `MorphologyGenotype` data omzet naar module-sets. Gebruik dit script om alle default creatures in content/bundles te migreren.

### 3. Physics & AI aansluiting (Week 3)
1. **`PhysicsBody` in movement** – vervang alle handmatige massaklemmen/dragformules in `movement.update_movement()` door de waarden uit `PhysicsBody`. Verifieer dat thrust/drag/volume consistent worden toegepast in acceleratie en energieverbruik.
2. **AI sensorherkoppeling** – update `ai.update_brain()` om `BodyGraph` traversal te gebruiken voor sensorgegevens (zichtkegel, elektromagnetisch bereik). Legacy “sensor_strength” velden kunnen dan verdwijnen.
3. **Hydro steering** – pas avoidance / stuck-logic aan naar fluid steering (stromingsvector + zachte dieptelimieten). Gebruik modulair `grip` en `drift_bias` uit modules voor beslissingen.

### 4. Wereld & voedselketen ombouw (Week 4)
1. **Nieuwe oceaangenerator** – implementeer `AbyssalOceanGenerator` als enige wereldbron, inclusief licht-/drukprofielen en stromingsvelden. Verwijder desert/jungle/archipelago varianten.
2. **Plankton & carrion entiteiten** – vervang `MossCluster` door `PlanktonCloud` en `SinkingCarcass` entiteiten die volumetrisch in het water hangen. Pas voedselconsumptie aan zodat creatures volume sampling gebruiken i.p.v. rect-collisions.
3. **Energy loop QA** – voer balancingtests uit (24h sim) om te bevestigen dat carrion-plankton-energiecircuits stabiel zijn binnen de nieuwe physics.

### 5. POC release criteria (Week 5)
1. **Feature freeze branch** – maak een `poc/ocean_modular` branch waarin alleen bugfixes worden gecherrypicked.
2. **Playable scenario** – configureer één scenario met 20 creatures (3 archetypes) in de nieuwe oceaan. Zorg voor logging van evolutiestatistieken, energiecurves en module-mutatierates.
3. **POC demo checklist** – documenteer setup-instructies, hardware-eisen, bekende issues en observatiepunten (bv. “let op modulair sensorbereik in twilight layer”) zodat stakeholders de sideways-ocean ervaring kunnen testen.
4. **Retrospective & go/no-go** – na een interne speelsessie wordt beslist of we full production ingaan; feedback wordt teruggevoerd naar roadmap Fase B/C.

### Deliverables & eigenaars
| Stap | Deliverable | Owner |
| --- | --- | --- |
| 1 | Gestabiliseerde BodyGraph API + tests | Systems Team |
| 2 | Modulegedreven spawning & reproductie | Gameplay Team |
| 3 | Physics & AI integratie | AI/Movement Team |
| 4 | Oceaanwereld + voedselketen | World Team |
| 5 | POC scenario + demo docs | Production |

Met dit schema migreren we gecontroleerd van legacy landcode naar het nieuwe modulaire oceaansysteem en hebben we binnen vijf weken een tastbaar POC om verdere investeringen te evalueren.

## Retro design language plan

Doel: een herkenbare “Ecco the Dolphin”-achtige identity neerzetten met 80's synthwave invloeden zonder de simulatie-realiteit te verliezen. Geen code, wel een uitvoerbaar plan dat art, UI en audio kunnen volgen.

### 1. Kernprincipes verzamelen
- **Referentieboard** – verzamel visuele referenties (Ecco 1/2, Amiga pixel art, Sega CD FMV, neon ocean posters). Curateer moodboards voor kleur, typografie en animatiecadans.
- **Color DNA** – definieer een 16-bit vriendelijk palet (max ±32 kleuren) met gradients voor zonlicht→abyss, aangevuld met neon accenten voor UI (magenta, teal, amber). Koppel elke laag (sunlit/twilight/etc.) aan 4–5 kernkleuren zodat artists consistent blijven.
- **Pixel grid discipline** – beslis of we 2x of 3x pixel-scaling gebruiken voor sprites en UI. Documenteer tilematen, parallaxlagen en ditheringregels zodat retro-look authentiek oogt.

### 2. Visuele taal vastleggen
- **Module silhouettes** – schets basishoudingen voor torso, vinnen, sensoren in een 16-bit sprite sheet. Gebruik contrasterende outline-kleuren zodat modulewissels leesbaar blijven binnen het retro palet.
- **UI kit** – ontwerp synthwave frames (chromed bevels, scanline overlays, chunky typography). Leg HUD-principes vast: energiebar met gradient + glans, depth-indicator als digitized sonar readout, menu's met neon grids.
- **FX library** – definieer pixel-animaties voor stromingen, bioluminescentie, carrion glows en module-activaties (thruster exhaust in 4 frames, sensor pulses als ellipsen). Beschrijf framerates en easing zodat engineers weten welke timing ze moeten targeten.

### 3. Audio en ambient cues
- **Soundtrack richting** – synth arpeggio's met delay + onderwater pads; schrijf een “sound bible” die per dieptelaag instrumentaties aanbeveelt (bovenlaag = marimba + chorus bass, abyss = detuned pads + gated reverb). Noem referenties (Vangelis, Tangerine Dream, Tim Follin).
- **SFX palette** – definieer layering (FM-synth blips + watery foley) voor UI clicks, module aanhechting, sonar pings. Beschrijf bitcrush/bandlimit zodat alles retro blijft maar toch modern mixbaar is.

### 4. Productieproces en tooling
- **Style guide document** – centraliseer bovenstaande keuzes in een Figma/Notion doc met downloadable palettes (.ase), sprite grids en typography specs (bitmap fonts + fallbacks).
- **Prototype sprint** – plan een 1-week art/UI sprint om drie deliverables te maken: (1) HUD mockup, (2) module sprite set (idle/boost), (3) environmental parallax slice (sunlit→twilight). Gebruik deze als referentie bij verdere implementatie.
- **Review ritme** – stel een wekelijkse “retro sync” in waarin art, UI, audio en gameplay checken of nieuwe assets voldoen aan palet/animatierichtlijnen. Log beslissingen zodat het DNA intact blijft tijdens featurewerk.

### 5. Integratie met POC
- **Touchpoints** – specificeer waar de stijl live gaat in de POC: splash screen, HUD, module inspectie UI, oceaanachtergrond en key FX. Roadmap deze items parallel aan de technische POC-stappen.
- **Technical handover** – lever engineers sprite atlases + shader notities (scanlines, chromatic aberration). Beschrijf fallback gedrag voor lage-res builds zodat retro look niet afhankelijk is van zware post-processing.

Met dit stappenplan krijgt elk discipline een duidelijk anker voor de retro gaming design taal voordat er code of assets worden vastgepind.

## Oceaanwereld

### Verticale kaartopbouw
- **Aspect ratio** – De nieuwe kaart is hoog en relatief smal (±1,2:1). Bij een viewport van 960×540 betekent dit ±6.000 px hoogte
  en 4.800 px breedte zodat creatures altijd ruimte hebben om in de diepte te bewegen.
- **Biome-lagen** – Vijf lagen (Surface / Sunlit / Twilight / Midnight / Abyss) krijgen elk **minimaal twee schermhoogtes** (≥1.080 px)
  zodat modules hun volle zweefruimte hebben. Camera-scroll blokkeert horizontaal licht maar laat verticale parallax toe.
- **Zijwand-geografie** – Procedurale kliffen en basaltrotsen worden uitsluitend langs de kaartzijden geplaats zodat de
  oceaanbodem open blijft. Meshes volgen een 16-bit “stair step” silhoutte voor retro leesbaarheid en bieden schuilplekken
  waar stromingen afbuigen.

### Dynamische systemen
- **Variabele stromingen** – `OceanPhysics` krijgt laag-specifieke vectorvelden met amplitude/noise curves geïnspireerd door
  *Ecco the Dolphin* en *Dave the Diver*: surface currents oscilleren langzaam, abyss currents pulseren in korte bursts. Dit voedt
  AI-stuurgedrag en achtergrond-animaties (ditheringstroken) voor een levendig retro gevoel.
- **Drukgradiënt** – Elke 400 px diepte verhoogt de druk +2 bar. Deze schaal voedt zowel physics (buoyancy modifiers) als HUD feedback
  (digitized sonar cijfers) zodat spelers intuïtief zien hoe gevaarlijk de diepte is.
- **Radioactieve vents** – In de Twilight/Midnight overgang spawnen “Rad Vents”: hexagonale rotsclusters met neon-gele rook en een
  rondom-liggend mutatieveld (radius 350 px). Creatures binnen de zone krijgen een verhoogde mutatiekans en risk/reward feedback in de
  evolutielogs. Het eerste framework bestaat uit: vent prefab, shader puls, mutation hook en telemetry event.
- **Pikdonkere abyss** – De onderste laag is volledig donker behalve voor bioluminescente flora en vent-licht. Shader-wise schakelen we
  over op een 2-bit palette met slechts cyan/purple highlight zodat spanning voelbaar is.

### Shader- en pixelrichtlijnen
- **Oppervlaktegolven** – Bovenaan renderen we een parallaxed wave strip (4-frame animatie, 12 fps) met scanline shader zodat het lijkt op
  een 16-bit tileset. De golven projecteren diffuse caustics naar beneden.
- **Lichtval** – Caustic shaders (GPU of CPU-driven) casten diagonale stroken die langzaam uitwaaieren en vervagen per laag. Animatie is
  tile-based (8×8 px) met offset scroll zodat het retro blijft maar toch dynamisch oogt.
- **Retro pixels** – Alles draait op het eerder gedefinieerde palette; cliffs, vents en kelp krijgen dithered gradients zodat ze consistent
  blijven met de retro design language.

### Biome-specifieke elementen
- **Sunlit/Surface** – Kelp forests en planktonwolken bewegen zacht mee met de stromingen; vissen zoeken beschutting tussen de zijwanden.
- **Twilight** – Radioactieve vents en chemosynthetische velden vormen upgrade hotspots, met ambient audio (Tangerine Dream pads) die het
  mystieke karakter benadrukken.
- **Midnight** – Sterke stromingswissels dwingen creatures hun BodyGraph-config (vinnen vs. thrusters) te bewijzen.
- **Abyss** – Pikdonker, langzaam vallende carrion en zeldzame glimrende mineralen die als navigatiepunten dienen.

### Content-hooks
- Vegetatie-masks bewegen verticaal mee zodat kelpwouden en chemosynthetische velden op verschillende dieptes kunnen bestaan.
- Nieuwe cliffs/vent assets sluiten aan op het modulair lichaamssysteem doordat grip surfaces en drukzones direct aan `BodyGraph` physics
  worden doorgegeven.
- Production kan deze blueprint gebruiken om de eerste POC van de sideways oceaanwereld te implementeren zonder later van stijl te hoeven
  wisselen.

### Module Viewer & Rendering Pipeline
- `tools/module_viewer.py` has evolved into a reference renderer for the modular bodies. It now draws polygons anchored to attachment points, builds a convex hull “skin” that excludes limbs, and renders fin/tentacle outlines with tapered geometry so attachments visually align with the underlying physics.
- Headless screenshot mode (`--screenshot`) and the `--pose sketch` preset let designers capture consistent visuals and iterate on the reference creature from the design sketch.
- Debug overlays (toggle with `J`) display joint markers and axes, enabling quick validation that the attachment math matches the physics body.
- These rendering upgrades now power the simulation too, so the viewer and in-game lifeforms share identical attachment-aware visuals.
