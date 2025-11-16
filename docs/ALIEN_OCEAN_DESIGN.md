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
