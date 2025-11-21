# Modular Jelly & Deep-Sea Body Plans

Deze notitie beschrijft hoe het nieuwe modulaire lichaamssysteem kan worden ingezet om diversere vormen te genereren die doen denken aan kwallen, octopus-achtige wezens en diepzee roofdieren.

## Basismodule: Jelly Bell
- **Klasse**: `JellyBell` (`bell_core`)
- **Rol**: centrale koepel met drijfvermogen, radiale tentakel-sockets en een centrale sifon voor pulsvoortstuwing.
- **Aanhechtingspunten**:
  - `siphon_nozzle` → `PulseSiphon` (ritmische jet die bell-compressies simuleert).
  - `umbrella_sensor` → compacte sensor (`SensorPod`) voor licht/bio-elektrische detectie in donkere lagen.
  - `tentacle_socket_*` → vier spier-gewrichten voor linttentakels met hoge swing-range (vluchtgedrag, omwikkelen van prooi).
- **Bioluminescence**: veld `bioluminescence` kan worden opgehoogd door mutaties voor signaal-/afschrikgedrag.

## Tentakels en voortstuwing
- **`TentacleLimb` (`tentacle`)**
  - Lange, lichte arm met grip- en thrust-component voor langzaam sturen.
  - Velden `venom_intensity` en `pulse_resonance` laten evolutie variëren tussen jagers (hoge venom, lage energie) en zwevers (lage venom, hoge resonance voor energiezuinig pulsen).
- **`PulseSiphon`**
  - Propulsionmodule met `pulse_frequency` die korte, dure bursts levert—geschikt voor vluchtgedrag of snelle opstijging.

## Groeirichtingen & mutaties
- **Sensorische differentiatie**: vervang `SensorPod` spectrum door sonar/thermal voor diepzee vissers; gebruik meerdere `umbrella_sensor` sockets via mutaties om een kroon van ogen te vormen.
- **Tentakelclusters**: duplicaties op `tentacle_socket_*` verhogen drag maar ook grip/energieopslag; torque-limieten per socket houden extreme combinaties in toom.
- **Jet-varianten**: swap `PulseSiphon` voor standaard `TailThruster` om hybride vormen (kwal + visstaart) te genereren.
- **Buoyancy tuning**: `buoyancy_bias` van bell en tentakels is positief; het systeem kan ballast (zwaardere materialen) toevoegen om abyss-habitat te bereiken zonder constante thrust.

## Render- en animatietips
- **Pulsatie**: de bell krijgt een lichte kroon + ring overlay; tentakels renderen als kromme lijnen met gloeiend uiteinde. Dit suggereert een zwembeweging ook zonder full-frame animatie.
- **Variatie**: kleuren/tints in `modular_palette` voor `bell_core` en `tentacle` verschillen duidelijk van vin/thruster-modules zodat populaties visueel divers zijn.

## Prototype blueprint
- De helper `build_jellyfish_prototype()` assembleert een bel, sifon, vier tentakels en een sensor: een basis drifter die kan evolueren richting zwever of roofdier door mutaties op thrust, grip en sensor-spectrum.
