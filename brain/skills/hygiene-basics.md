---
always: false
description: Pull in when planning bathrooms, placing toilets, showers, water tubs, plumbing, or when colonists have hygiene-related mood debuffs. Essential for Dubs Bad Hygiene mod.
name: hygiene-basics
tags:
- hygiene
- bathroom
- plumbing
- dubs-bad-hygiene
- water
- sewage
- mood
---

# Hygiene & Bathrooms (Dubs Bad Hygiene)

## The 3 Tiers of Hygiene (Progress as you research)

### Tier 1: Primitive (Early Game - No Research Needed)
- **Latrine (ส้วมหลุม):** 1x1, no water required, but needs to be emptied periodically by a colonist (Hauling job). Place in a small enclosed room (3x3 or 4x4) with a door for privacy.
- **Water Tub (อ่างอาบน้ำ):** 1x2, requires a Water source (Primitive Well or natural water tile nearby). Colonists bathe here. Needs refilling.
- **Primitive Well (บ่อน้ำหยาบ):** 2x2, place near the bathroom. Provides water for the tub.
- **Rule:** Build these IMMEDIATELY after the first beds. Do not wait for research.

### Tier 2: Plumbing (Mid Game - Requires "Plumbing" Research)
- **Piped Well (บ่อน้ำแบบท่อ):** 2x2, replaces Primitive Well. Provides infinite water if powered or hand-pumped.
- **Water Pump & Water Tower:** Build a pump next to the well, connect to a Water Tower (stores water for the colony). Connect with **Plumbing Pipes**.
- **Toilet (โถส้วม):** 1x1, requires plumbing. Replaces Latrine. Automatically flushes (no manual emptying).
- **Shower (ฝักบัว):** 1x2, requires plumbing. Faster than Water Tub.
- **Sewage Outlet (ท่อระบายน้ำเสีย):** CRITICAL. Connect toilets/showers to a Sewage Outlet that dumps into a river/lake. Without this, pipes back up and flood the base with waste.
- **Rule:** Upgrade to Toilets and Showers as soon as Plumbing is researched. Build a Sewage Outlet BEFORE placing the first Toilet.

### Tier 3: Advanced (Late Game - Requires "Advanced Plumbing" or "Central Heating")
- **Sewage Processor (เครื่องบำบัดน้ำเสีย):** Filters waste water back into clean water. Place near the Sewage Outlet.
- **Hot Water Tank (ถังน้ำร้อน):** Provides hot water for showers (mood bonus).
- **Rule:** Build these when you have surplus steel and components.

## Privacy Rules (Critical for Mood)
1. **One Toilet per Room:** Do NOT build a public bathroom with 4 toilets in one room. Colonists will get "Disturbed by privacy" mood penalties.
2. **Door Required:** Every bathroom MUST have a door. No exceptions.
3. **Size:** A bathroom for 1 person is 3x3. For 2 people (lovers), 4x4. For a barracks, build 2-3 small private bathrooms instead of one big one.
4. **Light:** Place a torch or lamp inside. Dark bathrooms cause "In darkness" penalties.

## Water & Sewage Infrastructure (The Pipe Network)
- **Water Pipes:** Connect Piped Well → Water Pump → Water Tower → Toilets/Showers. Use `rw_ui_build(def="Pipe")`.
- **Sewage Pipes:** Connect Toilets/Showers → Sewage Outlet. Use a separate pipe network or "Sewage Pipe" def.
- **Check Pressure:** Use `rw_state_power` or the mod's own UI to verify water pressure. If pressure is 0, colonists cannot use toilets and will have accidents (mood penalty + filth).
- **Sewage Outlet Placement:** Must be placed on a water tile (river, lake) or connected to a Sewage Processor. If placed on land, it creates a "Sewage Puddle" that causes disease.

## Mood Debuffs (What to Fix)
| Debuff | Cause | Fix |
|---|---|---|
| "Had to go in the bushes" | No toilet available | Build a Latrine or Toilet |
| "Used a dirty toilet" | Toilet not emptied (Tier 1) or no water pressure (Tier 2) | Empty the Latrine / Fix the pump |
| "Disturbed by privacy" | Toilet is in an open room or shared with others | Build individual stalls with doors |
| "Slept in filth" | Sewage backup or unemptied latrine | Fix sewage / Empty latrine |
| "Soaking wet" (in bathroom) | Water leak or overflow | Check pipes for damage |

## Building Order (Hygiene Focused)
1. **Day 1-3:** Build a 3x3 room with a Latrine and a Water Tub. Place a Primitive Well outside.
2. **Day 4-10:** Expand to 2 bathrooms if population grows (one per 2-3 colonists).
3. **Research Plumbing:** Priority #2 after Electricity. Then build Piped Well + Water Tower + Sewage Outlet.
4. **Upgrade:** Replace Latrines with Toilets and Water Tubs with Showers. Add Hot Water Tank for mood bonus.
5. **Late Game:** Build Sewage Processor to recycle water (saves on water source dependency).

## Common Mistakes
- **Building toilets without a Sewage Outlet:** The pipes will fill with waste and flood the base with filth. ALWAYS build the outlet first.
- **Building one giant bathroom:** Colonists will get privacy debuffs. Build small individual rooms.
- **Forgetting to empty Latrines (Tier 1):** The Latrine fills up after ~10 uses. If not emptied, it becomes a "full latrine" and colonist refuse to use it. Assign Hauling priority 1 to someone for this.
- **Placing a Water Tub far from water:** The colonist has to haul water manually. Place a Primitive Well right next to the tub.