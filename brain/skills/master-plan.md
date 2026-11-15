---
always: true
description: The master plan for building the colony. Use this to decide what to build next.
name: master-plan
tags: [planning, base-building, phases, survival]
---

# The Master Plan (Condition-Based Phases)
Do NOT rush the base. Do not use fixed days. Advance to the next phase ONLY when the condition is met. If a raid or disaster happens, drop back to survival mode (heal, repair, fight), then resume the plan.

## Phase 1: Survival & Shelter (Unlocks Phase 2 when completed)
**Goal:** Survive the first few days without dying.

- **Food (CRITICAL):** Find the BEST soil on the map (use `rw_map_detail` to look for rich soil). Distance does NOT matter; pawns can walk.
  - **Choose the best plant for the situation:** Use `rw_defs_buildable` or `rw_defs_search` to see what you can grow right now. Do NOT limit yourself to just rice or corn. Consider: 
    - *Fast survival:* Fast-growing crops if you are starving.
    - *Long term:* Slow-growing, high-yield crops if you have enough food.
    - *Environment:* Some crops survive cold or grow well in poor soil.
    - *Other:* Trees for wood, flowers for beauty, or medicinal plants if you need them.
  - Create a Growing Zone (`rw_ui_zone`) of at least 10 tiles per colonist. NEVER build on top of your growing zone; plan the base AROUND the fields.
  - **Force Farming:** Call `rw_steward_posture(label="harvest", hours=24)` to prioritize farming. If food_days is still low after 1 day, plant more.
- **Shelter:** Build a single room for beds. Make it just big enough for the current colonists + 1 extra bed. Use odd dimensions so the door is centered.
- **Hygiene:** Build a Latrine and Water Tub (see `hygiene-basics`).
- **Kitchen:** Build a Campfire or Stove with a cook bill. Put raw food stockpile NEXT to it.
- **Trigger to Phase 2:** You have beds, a toilet, a food field growing, and food_days > 3.

## Phase 2: Stability & Expansion (Unlocks Phase 3 when completed)
**Goal:** Expand into a proper base. Separate rooms.
- **Private Bedrooms:** Expand the barracks into separate bedrooms (one per colonist). Use shared walls to save materials. Size depends on the furniture (see `base-building`).
- **Storage:** Build a ROOFED storage room for food and materials. Unroofed items degrade.
- **Power (if researched):** Build a Wood-Fired Generator, Battery, and power lines to the kitchen and bedrooms (for lights/heaters).
- **Freezer:** Build a freezer room (2+ Coolers) to store meat and meals.
- **Trigger to Phase 3:** Every colonist has a private bed, food is stored under a roof, and you have a freezer running.

## Phase 3: The Perfect Base (Ongoing)
**Goal:** Build the "hub and spoke" layout. This is where the base becomes beautiful.
- **The Hub:** Build a central Dining/Recreation room (the biggest room in your base). Put tables, chairs, and a campfire/torch.
- **The Wings:** Build hallways (3 tiles wide) radiating from the hub. Place bedrooms on the left, workshops on the right, kitchen/freezer to the south.
- **The Wall:** Build an outer perimeter wall with exactly ONE entrance (the Chokepoint). This is for defense.
- **Trigger to Phase 4:** The Hub is built, the outer wall is up, and you have spare materials.

## Phase 4: Luxury & Defense
**Goal:** Make the colony self-sufficient and impossible to raid.
- **Defenses:** Turrets, Spike Traps, Sandbags at the Chokepoint.
- **Biodiversity:** Plant trees, flowers, or rare crops for beauty, resources, and mood. Do not just grow food; make the base look nice.
- **Animal Pen:** Build a proper pen (Fence + Gate + Marker + Grass) for livestock.
- **Better Hygiene:** Upgrade Latrines to Plumbing Toilets + Sewage Outlet.

## RULE: Don't forget the food!
If food_days drops below 5, PAUSE whatever you are doing, and fix the food immediately (Plant more, Harvest, Hunt). Do not build a fancy bedroom while your colonists are starving.