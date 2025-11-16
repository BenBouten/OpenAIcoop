# Alien Ocean Design

## Visie
- Evolutie-simulator
- Newtoniaanse fysica (position, velocity, forces, mass, drag, energy)
- Setting: Alien Ocean met dieptelagen (sunlit / twilight / dark / abyss)

## Kernsystemen
1. **DNA & traits** – genetische representatie van fysieke en gedragskenmerken.
2. **Lifeforms / creatures** – entiteiten die eigenschappen erven, muteren en evolueren.
3. **World / biomes** – generieke wereldlaag die later wordt uitgebreid naar oceaan-ecosystemen.
4. **Physics layer** – 2D newtoniaanse simulatie (top-down) in water met krachten en weerstand.
5. **Energy & fitness** – energiemodel gekoppeld aan fysica voor verbruik en efficiëntie.

## Roadmap
- **Fase A**: bestaande code opschonen en physics-fundament opzetten (componenten voor massa, krachten, energie).
- **Fase B**: creatures koppelen aan physics en energy/fitness-systemen voor evolutie-feedback.
- **Fase C**: wereld ombouwen naar oceaan-lagen (sunlit/twilight/dark/abyss) en water-specifieke traits toevoegen.

## Oceaanwereld
- Nieuwe "Abyssal Ocean" map: extreem hoge wereld (4800px) met vijf dieptelagen. De speler start bij de lichtgevende
  oppervlakte en kan naar beneden scrollen richting de pikdonkere bathyplaine.
- Elke laag is een biome met eigen modifiers (licht, voedsel, energie, druk). Hydrothermale vents en bioluminescente
  rifwanden zorgen voor hotspots voor voeding en energie.
- Vegetatie-masks verplaatsen zich nu verticaal om kelpwouden en chemosynthetische velden op verschillende dieptes te
  ondersteunen. Deze zones vormen de basis voor nieuwe zeewesens en toekomstige DNA-traits.
