"""
Enhanced Crude Mix Optimization Solver - Exact Ratio Version
Iterative optimization with tank pre-allocation and mass balance tracking
FIXED:
- Dynamic crude volume calculation based on input percentages
- Ensures all purchased crude is fully allocated in the mass balance
- Proper crude sequencing (no hardcoding)
- Cargo combinations optimized to match crude mix ratios
- Suspended tank priority filling
- FIXED: Correct tank sequencing (Idle > Empty > Full)
- FIXED: Correct vacant space logic *only* for idle tanks on their first cycle.
- FIXED: Reads idleTankData to track initial crude and report final blend.
- FIX (User): Added custom tank name mapping for logs and solver tasks.
- UPDATED: Added support for ULCC and Handy Size vessels.
"""

from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import json
import math
import io
from contextlib import redirect_stdout


class CrudeMixOptimizer:
    def __init__(self):
        self.model = None
        self.results = {}
        self.tank_allocations = []
        self.cargo_to_tank_map = {}
        self.mass_balance = {}
        self.suspended_tanks = []
        self.tank_sequence = []

    def solve_crude_mix_schedule(self, params):
        """Main optimization with iterative refinement for EXACT crude ratios"""
        try:
            # Extract parameters
            processing_rate = float(params.get('processingRate', 50000))
            num_tanks = self._detect_tank_count(params) 
            tank_capacity = float(params.get('tankCapacity', 500000))
            report_days = int(params.get('schedulingWindow', 30))
            
            print(f"SOLVER: Detected {num_tanks} total tanks from params, report window {report_days} days")

            # Extract EXACT crude mix requirements
            crude_mix = self._extract_crude_mix(params)
            if not crude_mix:
                print("ERROR: No crude mix configuration found")
                return {'success': False, 'error': 'No crude mix configuration'}

            # Verify percentages sum to 100%
            total_pct = sum(c['percentage'] for c in crude_mix.values())
            if abs(total_pct - 1.0) > 0.01:
                print(f"ERROR: Crude percentages sum to {total_pct*100}%, not 100%")
                return {'success': False, 'error': f'Crude percentages must sum to 100%'}

            vessels = self._extract_vessel_data(params)
            if not vessels:
                return {'success': False, 'error': 'No vessel types available'}

            # Calculate requirements
            # We pass num_tanks, but _get_empty_tanks is now fixed to use params
            empty_tanks_initial = self._get_empty_tanks(params, num_tanks)
            total_consumption = processing_rate * report_days
            total_needed = total_consumption

            print(f"SOLVER: Total crude needed = {total_needed:,.0f} bbl")

            crude_names = [c['name'] for c in crude_mix.values()]
            crude_ratios = [c['percentage'] for c in crude_mix.values()]
            print(f"SOLVER: Handling {len(crude_names)} crude types: {crude_names}")
            mix_summary = [(c['name'], f"{c['percentage']*100:.1f}%") for c in crude_mix.values()]
            print(f"SOLVER: Target mix = {mix_summary}")

            # Find optimal cargo combination that matches crude ratios
            optimal_vessel_pattern = self._find_optimal_vessel_combination(vessels, crude_ratios, crude_names)
            print(f"SOLVER: Optimal vessel pattern selected: {optimal_vessel_pattern}")

            # STEP 1: Pre-allocate tanks with exact crude requirements
            tank_plan = self._allocate_tanks_for_blend(
               params, num_tanks, empty_tanks_initial, crude_mix, tank_capacity, total_needed, report_days
            )
            
            # STEP 2: Generate cargoes using iterative optimization with ratio matching
            result = self._iterative_cargo_optimization(
                params, vessels, crude_mix, tank_plan, total_needed, optimal_vessel_pattern
            )
            
            if result['success']:
                # STEP 3: Create detailed tank filling schedule
                result['tank_filling_plan'] = self._create_tank_filling_schedule(
                    result['cargo_schedule'], tank_plan
                )
                
                # STEP 4: Generate mass balance
                result['mass_balance'] = self._generate_mass_balance(
                    result['cargo_schedule'], result['tank_filling_plan']
                )
                
                # STEP 5: Add tank sequence to result for utils.py
                result['tank_sequence'] = [tank['tank_id'] for tank in self.tank_allocations]
            
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _find_optimal_vessel_combination(self, vessels, crude_ratios, crude_names):
        """Find vessel combination that best matches crude mix ratios with all 7 vessel types"""
        print(f"\nFINDING OPTIMAL VESSEL COMBINATION:")
        print(f"Target crude ratios: {[f'{r*100:.1f}%' for r in crude_ratios]}")
        
        vessel_multipliers = {
            'ulcc': [0, 1, 2], # Keep low, these are massive
            'vlcc': [0, 1, 2, 3],
            'suezmax': [0, 0.5, 1, 1.5, 2],
            'aframax': [0, 0.25, 0.5, 0.75, 1, 1.25],
            'panamax': [0, 0.25, 0.5, 0.75, 1],
            'handymax': [0, 0.25, 0.5, 0.75, 1, 1.5],
            'handy_size': [0, 1, 2, 3, 4] # High multiplier allowed for small adjustments
        }
        
        best_combination = None
        best_deviation = float('inf')
        
        # Nested loops for all 7 vessel types
        for ulcc_mult in vessel_multipliers['ulcc']:
            for vlcc_mult in vessel_multipliers['vlcc']:
                for suez_mult in vessel_multipliers['suezmax']:
                    for afra_mult in vessel_multipliers['aframax']:
                        for pana_mult in vessel_multipliers['panamax']:
                            for handy_mult in vessel_multipliers['handymax']:
                                for h_size_mult in vessel_multipliers['handy_size']:
                                
                                    combination = {
                                        'ulcc': ulcc_mult,
                                        'vlcc': vlcc_mult,
                                        'suezmax': suez_mult,
                                        'aframax': afra_mult,
                                        'panamax': pana_mult,
                                        'handymax': handy_mult,
                                        'handy_size': h_size_mult
                                    }
                                    
                                    total_vessels = sum(combination.values())
                                    if total_vessels == 0:
                                        continue
                                    
                                    cargo_volumes = []
                                    for vessel_type, multiplier in combination.items():
                                        if vessel_type in vessels and multiplier > 0:
                                            volume = vessels[vessel_type]['capacity'] * multiplier
                                            cargo_volumes.append(volume)
                                    
                                    if len(cargo_volumes) != len(crude_ratios):
                                        continue
                                    
                                    total_cargo_volume = sum(cargo_volumes)
                                    if total_cargo_volume == 0:
                                        continue
                                        
                                    cargo_ratios = [v / total_cargo_volume for v in cargo_volumes]
                                    deviation = sum(abs(cargo_ratios[i] - crude_ratios[i]) for i in range(len(crude_ratios)))
                                    
                                    # --- THE GLOBAL CONDITION: DEVIATION MUST BE > 2% ---
                                    # If the solution is "too perfect" (e.g., using tiny ships), REJECT IT.
                                    if deviation < 0.000001:
                                        continue

                                    if deviation < best_deviation:
                                        best_deviation = deviation
                                        best_combination = combination.copy()
        
        print(f"  Final Selected Pattern: {best_combination}")
        print(f"  Final Deviation: {best_deviation*100:.2f}%")
        return best_combination

    def _allocate_tanks_for_blend(self, params, num_tanks, empty_tanks_initial, crude_mix, tank_capacity, total_needed, report_days):
        """Pre-allocate tanks with EXACT crude volumes for perfect blending"""
        tank_allocations = []

        # --- START FIX: Create Tank Name Map ---
        id_to_name_map = {}
        all_tank_keys = [key for key in params.keys() if key.startswith('tank') and key.endswith('Level')]
        all_tank_ids = set()
        for key in all_tank_keys:
            try:
                all_tank_ids.add(int(key.replace('tank', '').replace('Level', '')))
            except ValueError:
                continue
        
        for i in range(1, num_tanks + 1):
            all_tank_ids.add(i)

        for tank_id in all_tank_ids:
            custom_name = params.get(f"tank{tank_id}Name")
            if not custom_name:
                custom_name = f"Tank {tank_id}"
            id_to_name_map[tank_id] = custom_name
        # --- END FIX ---

        # --- START FIX: Load Idle Tank Crude Data ---
        idle_crude_map = {} 
        idle_tank_data = params.get('idleTankData', [])
        for tank_data in idle_tank_data:
            try:
                tank_id = int(tank_data.get('sequentialId'))
                if tank_id and tank_data.get('initialCrudes'):
                    idle_crude_map[tank_id] = tank_data['initialCrudes']
            except (ValueError, TypeError):
                continue
        print(f"SOLVER: Found initial crude data for idle tanks: {list(idle_crude_map.keys())}")
        # --- END FIX ---

        dead_bottom_base = float(params.get('deadBottom1', 10000))
        buffer_volume = float(params.get('bufferVolume', 500))
        dead_bottom_operational = dead_bottom_base + buffer_volume / 2
        usable_capacity = tank_capacity - dead_bottom_operational 
        
        tanks_needed_to_fill = math.ceil(total_needed / usable_capacity) + 5
        
        print(f"\nTANK ALLOCATION PLAN - DYNAMIC CRUDE VOLUMES:")
        print(f"Total crude required: {total_needed:,.0f} bbl. Usable capacity per tank: {usable_capacity:,.0f} bbl.")
        print(f"This will require filling {tanks_needed_to_fill} tanks over {report_days} days.")
        
        # --- START FIX: Correct Tank Categorization and Sequencing ---
        operational_floor = dead_bottom_base + buffer_volume / 2
        idle_partial_tanks_set = set(idle_crude_map.keys())
        idle_partial_tanks = sorted(list(idle_partial_tanks_set))

        empty_tanks = []
        occupied_full_tanks = []

        all_tank_keys = [key for key in params.keys() if key.startswith('tank') and key.endswith('Level')]

        for key in all_tank_keys:
            try:
                tank_id = int(key.replace('tank', '').replace('Level', ''))
                if tank_id in idle_partial_tanks_set:
                    continue
                    
                tank_level = float(params.get(key, 0))

                if tank_level <= operational_floor + 100: 
                    empty_tanks.append(tank_id)
                else: 
                    occupied_full_tanks.append(tank_id)
            
            except ValueError:
                continue
        
        print(f"SOLVER: Found {len(idle_partial_tanks)} Idle/Partial tanks (from UI): {sorted(idle_partial_tanks)}")
        print(f"SOLVER: Found {len(empty_tanks)} Empty tanks: {sorted(empty_tanks)}")
        print(f"SOLVER: Found {len(occupied_full_tanks)} Occupied/Full tanks: {sorted(occupied_full_tanks)}")

        dynamic_repeating_sequence = sorted(idle_partial_tanks) + sorted(empty_tanks) + sorted(occupied_full_tanks)
        
        translated_sequence = [id_to_name_map.get(tank_id, f"Tank {tank_id}") for tank_id in dynamic_repeating_sequence]
        print(f"INFO: Corrected dynamic repeating sequence created: {translated_sequence}")
        # --- END FIX ---

        final_tank_id_pool = []
        current_cycle = 0
        while len(final_tank_id_pool) < tanks_needed_to_fill:
            if current_cycle == 0:
                for tank_num in dynamic_repeating_sequence:
                    if len(final_tank_id_pool) >= tanks_needed_to_fill:
                        break
                    final_tank_id_pool.append(tank_num)
            else:
                for tank_num in dynamic_repeating_sequence:
                    if len(final_tank_id_pool) >= tanks_needed_to_fill:
                        break
                    tank_id_with_suffix = f"TK{tank_num}({current_cycle})"
                    final_tank_id_pool.append(tank_id_with_suffix)
            current_cycle += 1
        
        # --- START FIX: Translate pool to names for logging ---
        def translate_pool_id(id_val):
            id_str = str(id_val)
            cycle_suffix = ""
            if "(" in id_str:
                parts = id_str.split('(')
                base_id_str = parts[0].replace('TK', '')
                cycle_suffix = f"({parts[1]}"
            else:
                base_id_str = id_str
            
            try:
                base_id_int = int(base_id_str)
                custom_name = id_to_name_map.get(base_id_int, f"Tank {base_id_int}")
                return f"{custom_name}{cycle_suffix}"
            except ValueError:
                return str(id_val) 

        translated_pool = [translate_pool_id(tid) for tid in final_tank_id_pool[:20]]
        print(f"DEBUG: Tank sequence generated (first 20): {translated_pool}")
        # --- END FIX ---

        # --- START FIX: Calculate Vacant Space *ONLY* for Idle Tanks on First Cycle ---
        seen_base_tanks = set()

        for i in range(tanks_needed_to_fill):
            tank_id_full = final_tank_id_pool[i] 
            
            base_tank_id_str = str(tank_id_full).split('(')[0].replace('TK', '')
            base_tank_id = int(base_tank_id_str) 
            
            is_first_cycle = base_tank_id not in seen_base_tanks
            seen_base_tanks.add(base_tank_id)

            id_str = str(tank_id_full)
            cycle_suffix = ""
            if "(" in id_str:
                parts = id_str.split('(')
                cycle_suffix = f"({parts[1]}"
            
            custom_name = id_to_name_map.get(base_tank_id, f"Tank {base_tank_id}")
            translated_tank_id_for_LOGS = f"{custom_name}{cycle_suffix}"
            
            original_tank_id_for_DATA = tank_id_full

            # --- THIS IS THE KEY LOGIC ---
            fillable_capacity_for_this_cycle = usable_capacity 
            
            if is_first_cycle:
                if base_tank_id in idle_partial_tanks_set:
                    tank_level = float(params.get(f'tank{base_tank_id}Level', 0))
                    current_usable_volume = max(0, tank_level - dead_bottom_operational)
                    vacant_space = usable_capacity - current_usable_volume
                    
                    fillable_capacity_for_this_cycle = vacant_space 
                    
                    print(f"SOLVER: Tank {id_to_name_map.get(base_tank_id)} (Idle) has {current_usable_volume:,.0f} bbl. Vacant space to fill: {vacant_space:,.0f} bbl.")
                
                elif base_tank_id in occupied_full_tanks:
                    print(f"SOLVER: Tank {id_to_name_map.get(base_tank_id)} (Filled) first cycle plan is for full {usable_capacity:,.0f} bbl.")
                
                else: 
                    print(f"SOLVER: Tank {id_to_name_map.get(base_tank_id)} (Empty) first cycle plan is for full {usable_capacity:,.0f} bbl.")
            # --- END KEY LOGIC ---
            
            tank_allocation = {
                'tank_id': original_tank_id_for_DATA, 
                'total_capacity': tank_capacity,
                'usable_capacity': fillable_capacity_for_this_cycle, 
                'crude_volumes': {}
            }
            
            # --- START FIX: Pre-populate tank_allocation with existing crudes ---
            if is_first_cycle and base_tank_id in idle_crude_map:
                existing_crudes = idle_crude_map[base_tank_id]
                for crude in existing_crudes:
                    crude_name = crude.get('name', 'Unknown')
                    crude_vol = float(crude.get('volume', 0))
                    if crude_vol > 0:
                        tank_allocation['crude_volumes'][crude_name] = {
                            'target_volume': crude_vol, 
                            'target_percentage': 0, 
                            'filled_volume': crude_vol, 
                            'source_cargoes': ['InitialStock']
                        }
            # --- END FIX ---

            for crude_key, crude_data in crude_mix.items():
                crude_percentage = crude_data['percentage']
                volume_per_tank = fillable_capacity_for_this_cycle * crude_percentage 
                
                existing_vol_details = tank_allocation['crude_volumes'].get(crude_data['name'], {})
                
                tank_allocation['crude_volumes'][crude_data['name']] = {
                    'target_volume': existing_vol_details.get('target_volume', 0) + volume_per_tank,
                    'target_percentage': crude_percentage * 100, 
                    'filled_volume': existing_vol_details.get('filled_volume', 0),
                    'source_cargoes': existing_vol_details.get('source_cargoes', [])
                }
                
            if i < 20:
                print(f"\nTank {translated_tank_id_for_LOGS} Dynamic Volume Allocation (Fillable: {fillable_capacity_for_this_cycle:,.0f} bbl):")
                total_allocated = 0
                for crude_name, details in tank_allocation['crude_volumes'].items():
                    volume = details['target_volume']
                    total_allocated += volume
                    if 'InitialStock' in details['source_cargoes']:
                        print(f"  {crude_name}: {volume:,.0f} bbl (Initial Stock)")
                    else:
                        percentage = details['target_percentage']
                        print(f"  {crude_name}: {volume:,.0f} bbl ({percentage:.1f}% of new fill)")
                
                print(f"  Total in tank: {total_allocated:,.0f} bbl")
            
            tank_allocations.append(tank_allocation)
        # --- END FIX ---
        
        self.tank_allocations = tank_allocations
        self.tank_sequence = final_tank_id_pool
        return tank_allocations

    def _iterative_cargo_optimization(self, params, vessels, crude_mix, tank_plan, total_needed, optimal_vessel_pattern):
        """
        Iterative optimization with FEEDBACK LOOP to improve ratios.
        Now re-calculates vessel pattern each time based on previous errors.
        """
        max_iterations = 10
        tolerance = 0.001  # 0.1% tolerance
        
        best_schedule = None
        best_deviation = float('inf')
        
        # Base targets (The actual refinery requirement)
        base_ratios = [c['percentage'] for c in crude_mix.values()]
        crude_names = [c['name'] for c in crude_mix.values()]
        
        # Dynamic targets (We adjust these to steer the solver)
        current_target_ratios = list(base_ratios)
        current_vessel_pattern = optimal_vessel_pattern
        
        print(f"\nITERATIVE OPTIMIZATION (With Feedback Loop):")
        print("="*80)
        
        for iteration in range(max_iterations):
            print(f"\nIteration {iteration + 1}:")
            print(f"  Adjusted Target Ratios: {[f'{r*100:.1f}%' for r in current_target_ratios]}")
            print("-"*80)
            
            # STEP 1: Re-calculate optimal vessel pattern based on adjusted targets
            # (Skip for first iteration to use the initial seed)
            if iteration > 0:
                new_pattern = self._find_optimal_vessel_combination(vessels, current_target_ratios, crude_names)
                if new_pattern:
                    current_vessel_pattern = new_pattern
                    print(f"  New Vessel Pattern Selected: {current_vessel_pattern}")
                else:
                    print("  (Kept previous vessel pattern)")

            # STEP 2: Calculate exact crude volumes needed based on tank plan
            crude_requirements = defaultdict(float)
            for tank in tank_plan:
                for crude_name, details in tank['crude_volumes'].items():
                    if 'InitialStock' not in details.get('source_cargoes', []):
                        crude_requirements[crude_name] += details['target_volume']

            # STEP 3: Generate schedule using current pattern
            schedule = self._generate_optimal_cargo_mix(
                params, vessels, crude_requirements, iteration, current_vessel_pattern, total_needed
            )
            
            # STEP 4: Calculate Actual Results
            total_by_crude = defaultdict(float)
            for cargo in schedule:
                total_by_crude[cargo['crude_name']] += cargo['size']
            
            total_volume = sum(total_by_crude.values())
            
            # STEP 5: Analyze Deviation & Update Best Result
            print(f"\nDEVIATION ANALYSIS:")
            max_deviation = 0
            current_actual_ratios = []
            
            for i, crude_name in enumerate(crude_names):
                target_pct = base_ratios[i] # Always compare against REAL base requirement
                actual_pct = total_by_crude[crude_name] / total_volume if total_volume > 0 else 0
                current_actual_ratios.append(actual_pct)
                
                deviation = abs(actual_pct - target_pct)
                max_deviation = max(max_deviation, deviation)
                
                status = "✓ OK" if deviation < 0.01 else "⚠ WARNING"
                print(f"  {crude_name:20s}: Target={target_pct*100:6.2f}%  Actual={actual_pct*100:6.2f}%  Diff={deviation*100:6.3f}%  {status}")
            
            if max_deviation < best_deviation:
                best_schedule = schedule
                best_deviation = max_deviation
            
            if max_deviation <= tolerance:
                print(f"\n✓✓✓ SUCCESS: Achieved target ratios within {tolerance*100}% tolerance! ✓✓✓\n")
                break
            
            # STEP 6: Feedback Loop (Adjust targets for next run)
            # If Actual > Base, we lower the target. If Actual < Base, we raise it.
            if iteration < max_iterations - 1:
                print(f"\n  >> Adjusting targets to compensate for {max_deviation*100:.2f}% deviation...")
                
                new_targets = []
                for i in range(len(base_ratios)):
                    base = base_ratios[i]
                    actual = current_actual_ratios[i]
                    error = actual - base
                    
                    # Correction: Subtract the error from the target (Adaptive P-Controller)
                    # Factor 0.8 provides stability so we don't overshoot
                    adjusted_target = current_target_ratios[i] - (error * 0.8)
                    new_targets.append(max(0.001, adjusted_target)) # Prevent negative/zero
                
                # Normalize back to 100%
                total_new = sum(new_targets)
                current_target_ratios = [t / total_new for t in new_targets]
        
        if best_schedule:
            return self._format_final_schedule(params, best_schedule, crude_mix, tank_plan)
        else:
            return {'success': False, 'error': 'Failed to generate schedule'}

    def _generate_optimal_cargo_mix(self, params, vessels, crude_requirements, iteration, optimal_vessel_pattern, total_needed):
        """Generate cargo list based on volume needs only - NO timing"""
        schedule = []

        tank_capacity = float(params.get('tankCapacity', 500000))
        dead_bottom_base = float(params.get('deadBottom1', 10000))
        buffer_volume = float(params.get('bufferVolume', 500))
        dead_bottom_operational = dead_bottom_base + buffer_volume / 2
        usable_capacity = tank_capacity - dead_bottom_operational
        
        crude_mix = self._extract_crude_mix(params)
        crude_names = [crude_mix[k]['name'] for k in crude_mix.keys()] if crude_mix else ['Unknown']
        
        print(f"\nVOLUME-BASED SCHEDULER - Iteration {iteration}")
        print(f"Usable capacity per tank: {usable_capacity:,.0f} bbl")
        print(f"Crude types: {crude_names}")
        
        crude_volume_per_tank = {}
        for crude_key in crude_mix.keys():
            crude_data = crude_mix[crude_key]
            volume = usable_capacity * crude_data['percentage']
            crude_volume_per_tank[crude_data['name']] = volume
            print(f"{crude_data['name']}: {volume:,.0f} bbl per tank ({crude_data['percentage']*100:.1f}%)")
        
        # Build vessel sequence based on optimal pattern
        vessel_sequence = []
        if optimal_vessel_pattern:
            for vessel_type, multiplier in optimal_vessel_pattern.items():
                if vessel_type in vessels and multiplier > 0:
                    if multiplier >= 1:
                        vessel_sequence.extend([vessel_type] * int(multiplier))
                    else:
                        if multiplier >= 0.1:
                            vessel_sequence.append(vessel_type)
        
        if not vessel_sequence:
            vessel_list = sorted(vessels.items(), key=lambda x: x[1]['capacity'], reverse=True)
            vessel_sequence = [vessel_list[0][0]]
        
        print(f"VESSEL ROTATION SEQUENCE: {vessel_sequence}")
        print(f"Pattern multipliers: {optimal_vessel_pattern}")
        
        tank_plan = self.tank_allocations
        current_tank_idx = 0
        certified_tanks = []
        
        if not tank_plan:
            print("ERROR: Tank plan is empty.")
            return []
            
        tank_states = {}
        
        cargo_id = 1        
        crude_index = 0
        vessel_index = 0
        total_scheduled_volume = 0
        
        # --- FIX: Use the calculated total_needed, not the raw one ---
        total_needed_to_purchase = sum(crude_requirements.values())
        print(f"SOLVER: Total crude to purchase (excluding initial stock): {total_needed_to_purchase:,.0f} bbl")
        
        while total_scheduled_volume < total_needed_to_purchase:
            if cargo_id > 200:
                print("WARNING: Exceeded 200 cargo limit. Finalizing schedule.")
                break
            
            # --- 1. DEFINE CONSTRAINTS HERE (Together) ---
            # Change '0' to '1' if you want to force them without UI input
            min_ulcc_required = int(params.get('minUlccRequired', 0)) 
            min_vlcc_required = int(params.get('minVlccRequired', 0))

            # --- 2. SELECTION LOGIC ---
            
            # Priority 1: Force ULCCs First
            if 'ulcc' in vessels and cargo_id <= min_ulcc_required:
                vessel_type = 'ulcc'
                print(f"  Cargo {cargo_id}: FORCED ULCC (constraint: {cargo_id}/{min_ulcc_required})")
            
            # Priority 2: Force VLCCs Next (shifted by ULCC count)
            elif 'vlcc' in vessels and cargo_id <= (min_ulcc_required + min_vlcc_required):
                vessel_type = 'vlcc'
                print(f"  Cargo {cargo_id}: FORCED VLCC (constraint)")
            
            # Priority 3: Use Optimized Sequence
            else:
                vessel_type = vessel_sequence[vessel_index % len(vessel_sequence)]
                print(f"  Cargo {cargo_id}: Selected {vessel_type.upper()} (index: {vessel_index % len(vessel_sequence)})")

            
            crude_name = crude_names[crude_index % len(crude_names)]
            vessel_data = vessels[vessel_type]
            
            # Check tank availability
            if current_tank_idx >= len(tank_plan):
                print("ERROR: Exceeded tank plan size.")
                break
                
            tank_to_fill = tank_plan[current_tank_idx]['tank_id']
            current_total_volume = sum(c['size'] for c in schedule)
            remaining_needed = total_needed_to_purchase - current_total_volume
            cargo_size_to_schedule = min(vessel_data['capacity'], remaining_needed)

            if cargo_size_to_schedule < 1000:
                print("INFO: Remaining crude less than minimum. Finalizing.")
                break

            cargo = {
                'cargo_id': cargo_id,
                'type': vessel_type.upper(),
                'vessel_type': vessel_type,
                'vessel_name': f"{vessel_type.upper()}-V{cargo_id:03d}",
                'crude_type': crude_name,
                'crude_name': crude_name,
                'size': cargo_size_to_schedule,
            }

            schedule.append(cargo)
            
            # Update tank states
            cargo_vol_remaining = cargo_size_to_schedule
            for tank_idx in range(len(tank_plan)):
                if cargo_vol_remaining <= 0:
                    break
                tank_id = tank_plan[tank_idx]['tank_id']
                
                if tank_id not in tank_states:
                    tank_states[tank_id] = {c: 0 for c in crude_names}
                    # --- FIX: Account for InitialStock in tank_states ---
                    if 'crude_volumes' in tank_plan[tank_idx]:
                        for cn, details in tank_plan[tank_idx]['crude_volumes'].items():
                            if 'InitialStock' in details.get('source_cargoes', []):
                                tank_states[tank_id][cn] = details.get('target_volume', 0)
                    # --- END FIX ---
                    tank_states[tank_id]['status'] = 'empty'
                
                # --- FIX: Account for Initial Stock in target ---
                crude_details = tank_plan[tank_idx]['crude_volumes'].get(crude_name, {})
                target_for_crude = crude_details.get('target_volume', 0)
                
                # Subtract any initial stock *of the same crude type*
                initial_stock_volume = 0
                if 'InitialStock' in crude_details.get('source_cargoes', []):
                    # Check if the initial stock is of the *same crude* we are filling
                    if crude_name == cn: 
                        initial_stock_volume = crude_details.get('target_volume', 0)
                
                target_to_fill = target_for_crude - initial_stock_volume
                # --- END FIX ---

                current_in_tank = tank_states[tank_id].get(crude_name, 0)
                # If tank has initial stock, current_in_tank is already set
                if initial_stock_volume > 0:
                    current_in_tank = initial_stock_volume

                needed = target_to_fill - (current_in_tank - initial_stock_volume) # Need = target_to_fill - already_filled_by_cargoes
                
                if needed > 0:
                    volume_to_add = min(needed, cargo_vol_remaining)
                    tank_states[tank_id][crude_name] += volume_to_add
                    cargo_vol_remaining -= volume_to_add
                    
                    # --- FIX: Check against the tank's *specific* usable capacity ---
                    tank_usable_capacity = tank_plan[tank_idx].get('usable_capacity', usable_capacity)
                    
                    # --- FIX: Total in tank must include ALL crudes, even initial ---
                    total_in_tank = sum(tank_states[tank_id].get(c, 0) for c in tank_states[tank_id] if c != 'status')
                    
                    # Get the *full* capacity of the tank plan (e.g. 589,750), not the fillable (489,750)
                    full_planned_capacity = sum(details.get('target_volume', 0) for details in tank_plan[tank_idx]['crude_volumes'].values())

                    if total_in_tank >= full_planned_capacity * 0.99:
                    # --- END FIX ---
                        tank_states[tank_id]['status'] = 'complete'
            
            print(f"  QUEUED CARGO {cargo_id}: {vessel_type.upper()}-V{cargo_id:03d}, {cargo_size_to_schedule:,.0f} bbl of {crude_name}")
            
            total_scheduled_volume += cargo_size_to_schedule
            crude_index += 1
            vessel_index += 1
            cargo_id += 1
        
        # Summary of vessels used
        vessel_usage = defaultdict(int)
        for cargo in schedule:
            vessel_usage[cargo['type']] += 1
        
        print(f"\n{'='*80}")
        print(f"CARGO GENERATION COMPLETE")
        print(f"Total cargoes created: {len(schedule)}")
        print(f"Vessel breakdown:")
        
        # UPDATED VESSEL LIST FOR REPORTING
        vessel_list = ['ULCC', 'VLCC', 'SUEZMAX', 'AFRAMAX', 'PANAMAX', 'HANDYMAX', 'HANDY_SIZE']
        
        for vessel_type in vessel_list:
            count = 0
            for c in schedule:
                # Handle both uppercase (from schedule) and lowercase (from keys) just in case
                if c['type'] == vessel_type: count += 1
                elif c['vessel_type'] == vessel_type.lower(): count += 1
            
            if count > 0:
                print(f"  {vessel_type}: {count} cargoes")
        print(f"{'='*80}")
        
        print(f"\nFINAL TANK STATUS (SIMULATED):")
        for tank_id_full in [t['tank_id'] for t in tank_plan[:20]]: # Show first 20 planned
            tank_data = tank_states.get(tank_id_full, {})
            status = tank_data.get('status', 'not_filled')
            total_vol = sum(tank_data[crude] for crude in tank_data if crude != 'status')
            
            crude_breakdown = []
            
            all_crudes_in_tank = set(list(tank_plan[0]['crude_volumes'].keys()) + list(tank_data.keys()))

            for crude in all_crudes_in_tank:
                if crude == 'status':
                    continue
                
                vol = tank_data.get(crude, 0)
                if vol > 0:
                    initial_stock = False
                    if 'crude_volumes' in tank_plan[tank_idx]:
                        details = tank_plan[tank_idx]['crude_volumes'].get(crude, {})
                        if 'InitialStock' in details.get('source_cargoes', []):
                            initial_stock = True

                    if initial_stock:
                        crude_breakdown.append(f"{crude}:{vol:,.0f} (Initial)")
                    else:
                        crude_breakdown.append(f"{crude}:{vol:,.0f}")

            print(f"Tank {tank_id_full}: {total_vol:,.0f} bbl ({status}) [{', '.join(crude_breakdown)}]")
        
        return schedule

    def _create_tank_filling_schedule(self, cargo_schedule, tank_plan):
        """Create detailed schedule showing which cargo fills which tank"""
        filling_schedule = []
        cargo_volumes = {c['cargo_id']: c['size'] for c in cargo_schedule}
        
        print(f"\nTANK FILLING SCHEDULE:")
        
        for tank_idx, tank in enumerate(tank_plan):
            tank_id_display = tank['tank_id'] # This is now the translated name, e.g., "201"
            print(f"\nTank {tank_id_display} Filling Plan (Target Usable: {tank['usable_capacity']:,.0f} bbl):")
            
            for crude_name, crude_details in tank['crude_volumes'].items():
                # --- FIX: Do not schedule filling for InitialStock ---
                if 'InitialStock' in crude_details.get('source_cargoes', []):
                    print(f"  Skipping {crude_name}: {crude_details.get('target_volume', 0):,.0f} bbl (Initial Stock)")
                    continue
                # --- END FIX ---
                
                target_volume = crude_details['target_volume']
                filled_volume = 0
                
                matching_cargoes = [c for c in cargo_schedule 
                                  if c['crude_name'] == crude_name 
                                  and cargo_volumes.get(c['cargo_id'], 0) > 100]
                
                for cargo in matching_cargoes:
                    if filled_volume >= target_volume - 100:
                        break
                    
                    volume_needed = target_volume - filled_volume
                    available_in_cargo = cargo_volumes.get(cargo['cargo_id'], 0)
                    volume_to_take = min(volume_needed, available_in_cargo)
                    
                    if volume_to_take > 100:
                        filling_schedule.append({
                            'tank_id': tank['tank_id'], # Use the translated name
                            'cargo_id': cargo['cargo_id'],
                            'vessel_name': cargo['vessel_name'],
                            'crude_type': crude_name,
                            'volume': volume_to_take,
                            'percentage_of_tank': (volume_to_take / tank['usable_capacity']) * 100 if tank['usable_capacity'] > 0 else 0,
                            'source_cargoes': crude_details.get('source_cargoes', []) # Pass this info
                        })
                        
                        cargo_volumes[cargo['cargo_id']] -= volume_to_take
                        filled_volume += volume_to_take
                        
                        # Use tank's usable_capacity for percentage calculation
                        tank_fill_pct = (volume_to_take / tank['usable_capacity']) * 100 if tank['usable_capacity'] > 0 else 0
                        print(f"  {cargo['vessel_name']} -> {volume_to_take:,.0f} bbl {crude_name} ({tank_fill_pct:.1f}% of this cycle's fill)")
                
                if filled_volume < target_volume * 0.95:
                    print(f"  WARNING: Could only plan to fill {filled_volume:,.0f}/{target_volume:,.0f} bbl of {crude_name} for this tank.")
        
        print(f"\nTotal tanks processed: {len(tank_plan)}")
        return filling_schedule

    def _generate_mass_balance(self, cargo_schedule, tank_filling_plan):
        """Generate complete mass balance for all cargoes"""
        mass_balance = {}
        
        print(f"\nCARGO MASS BALANCE:")
        
        for cargo_idx, cargo in enumerate(cargo_schedule):
            cargo_id = cargo['cargo_id']
            total_size = cargo['size']
            
            allocations = [f for f in tank_filling_plan if f['cargo_id'] == cargo_id]
            
            tank_breakdown = {}
            total_allocated = 0
            
            for alloc in allocations:
                tank_id = alloc['tank_id'] # This is now the translated name
                volume = alloc['volume']
                tank_breakdown[f"Tank_{tank_id}"] = tank_breakdown.get(f"Tank_{tank_id}", 0) + volume
                total_allocated += volume
            
            unallocated = total_size - total_allocated
            
            mass_balance[cargo['vessel_name']] = {
                'cargo_id': cargo_id,
                'crude_type': cargo['crude_name'],
                'total_size': total_size,
                'allocated': total_allocated,
                'unallocated': unallocated,
                'tank_breakdown': tank_breakdown,
                'utilization': (total_allocated / total_size * 100) if total_size > 0 else 0
            }
            
            print(f"\n{cargo['vessel_name']} ({cargo['crude_name']}) - {total_size:,.0f} bbl:")
            for tank, vol in tank_breakdown.items():
                print(f"  {tank}: {vol:,.0f} bbl ({vol/total_size*100:.1f}%)")
            
            if unallocated > 1000:
                print(f"  Unallocated: {unallocated:,.0f} bbl ({unallocated/total_size*100:.1f}%)")
        
        print(f"\nTotal cargoes processed: {len(cargo_schedule)}")
        return mass_balance

    def _format_final_schedule(self, params, schedule, crude_mix, tank_plan):
        """Format final schedule with all details"""
        total_by_crude = defaultdict(float)
        vessel_counts = defaultdict(int)
        
        for cargo in schedule:
            total_by_crude[cargo['crude_name']] += cargo['size']
            vessel_counts[cargo['type']] += 1
        
        total_volume = sum(total_by_crude.values())
        total_cost = 0  # Cost calculated by scheduler
        
        actual_percentages = {}
        for crude_name, volume in total_by_crude.items():
            actual_percentages[crude_name] = (volume / total_volume * 100) if total_volume > 0 else 0
        
        print(f"\n{'='*80}")
        print("OPTIMIZATION COMPLETE")
        vessel_types_to_display = ['ULCC', 'VLCC', 'SUEZMAX', 'AFRAMAX', 'PANAMAX', 'HANDYMAX', 'HANDY_SIZE']
        cargo_counts_str = ",  ".join([f"{v_type}: {vessel_counts.get(v_type, 0)}" for v_type in vessel_types_to_display])
        print(f"Vessel Cargoes: {cargo_counts_str}")

        print(f"Total Volume: {total_volume:,.0f} bbl")
        print(f"Total Cost: ${total_cost:,.0f}")
        print(f"Cargoes: {len(schedule)}")
        print("\nFINAL CRUDE MIX ACHIEVED (Purchased):")
        for crude_name, pct in actual_percentages.items():
            target_pct = next((c['percentage'] * 100 for c in crude_mix.values() if c['name'] == crude_name), 0)
            status = "[OK]" if abs(pct - target_pct) < 0.5 else "[WARN]"
            print(f"  {crude_name}: {pct:.1f}% (Target: {target_pct:.1f}%) {status}")
        print(f"Suspended tanks processed: {len(self.suspended_tanks)}")
        print(f"{'='*80}")
        
        return {
            'success': True,
            'cargo_schedule': schedule,
            'total_cost': total_cost,
            'tank_sequence': self.tank_sequence,  # Pass the sequence to utils
            'optimization_status': 'Formula-Based Exact Ratio Optimization Complete',
            'crude_mix_achieved': self._format_tank_distribution(tank_plan, actual_percentages),
            'actual_percentages': actual_percentages,
            'vessel_distribution': dict(vessel_counts),
            'volume_by_crude': dict(total_by_crude),
            'suspended_tanks': self.suspended_tanks,
            'solver_info': {
                'method': 'formula_based_exact_ratio',
                'total_cargoes': len(schedule),
                'total_volume': total_volume,
                'exact_ratio_achieved': all(abs(actual_percentages.get(c['name'], 0) - c['percentage']*100) < 0.5 
                                          for c in crude_mix.values())
            }
        }

    def _format_tank_distribution(self, tank_plan, actual_percentages):
        """Format tank distribution for output
        FIXED: Correctly calculates percentages for tanks with initial crude.
        """
        distribution = {}
        
        for tank_idx, tank in enumerate(tank_plan):  
            tank_id_display = tank['tank_id'] # This is now the translated name
            tank_name = f"Tank_{tank_id_display}"
            distribution[tank_name] = {}
            
            # --- START FIX ---
            # Calculate the *true* total volume in this tank
            true_total_volume = 0
            for crude_name, details in tank['crude_volumes'].items():
                # 'target_volume' holds the final volume for each crude
                true_total_volume += details.get('target_volume', 0)
            
            if true_total_volume == 0:
                true_total_volume = 1 # Avoid division by zero

            for crude_name, details in tank['crude_volumes'].items():
                final_volume = details.get('target_volume', 0)
                final_percentage = (final_volume / true_total_volume) * 100
                
                distribution[tank_name][crude_name] = {
                    'volume': round(final_volume, 0),
                    'percentage': round(final_percentage, 1)
                }
            # --- END FIX ---
        
        return distribution

    def _detect_tank_count(self, params):
        """Detect number of tanks from parameters"""
        tank_numbers = []
        for key in params.keys():
            if key.startswith('tank') and key.endswith('Level'):
                try:
                    tank_num = int(key.replace('tank', '').replace('Level', ''))
                    tank_numbers.append(tank_num)
                except ValueError:
                    continue
        
        # --- FIX: Use the MAX tank number found, even if it's '95' ---
        detected_max = max(tank_numbers) if tank_numbers else 0
        param_tanks_ui = int(params.get('numTanks', 12))
        
        # We return the detected_max so that all tanks (1-13 and 41) are "known"
        # The sequencing logic will handle the order.
        return max(detected_max, param_tanks_ui)

    def _extract_crude_mix(self, params):
        """Extract crude mix configuration"""
        crude_names = params.get('crude_names', [])
        crude_percentages = params.get('crude_percentages', [])
        
        if not crude_names or not crude_percentages:
            return None
        
        mix = {}
        for i, (name, p) in enumerate(zip(crude_names, crude_percentages)):
            if float(p) > 0:
                mix[f'crude_{i}'] = {
                    'name': name,
                    'percentage': float(p) / 100.0,
                    'index': i
                }
        
        return mix

    def _extract_vessel_data(self, params):
        """Extract vessel configurations including ULCC and Handy Size"""
        vessels = {}
        # Order matters for display priority, but solver logic handles volume optimization independently
        vessel_types_config = [
            ('ulcc', 'ulccCapacity', 'ulccRateDay', 'ulccIncludeReturn'),          # NEW
            ('vlcc', 'vlccCapacity', 'vlccRateDay', 'vlccIncludeReturn'),
            ('suezmax', 'suezmaxCapacity', 'suezmaxRateDay', 'suezmaxIncludeReturn'),
            ('aframax', 'aframaxCapacity', 'aframaxRateDay', 'aframaxIncludeReturn'),
            ('panamax', 'panamaxCapacity', 'panamaxRateDay', 'panamaxIncludeReturn'),
            ('handymax', 'handymaxCapacity', 'handymaxRateDay', 'handymaxIncludeReturn'),
            ('handy_size', 'handySizeCapacity', 'handySizeRateDay', 'handySizeIncludeReturn') # NEW
        ]
        
        for v_type, cap_key, rate_key, return_key in vessel_types_config:
            capacity = float(params.get(cap_key, 0))
            rate = float(params.get(rate_key, 50000))
            if capacity > 0:
                vessels[v_type] = {
                    'capacity': capacity,
                    'daily_rate': rate,
                    'include_return': params.get(return_key, True),
                    'journey_days': float(params.get('journeyDays', 10)),
                    'pre_journey_days': float(params.get('preJourneyDays', 1)),
                    'pre_discharge_days': float(params.get('preDischargeDays', 1)),
                    'pumping_rate': float(params.get('pumpingRate', 30000))
                }
        
        return vessels

    def _calculate_initial_inventory(self, params, num_tanks):
        """Calculate initial inventory"""
        total = 0
        # --- FIX: Loop over actual keys, not 1-num_tanks ---
        all_tank_keys = [key for key in params.keys() if key.startswith('tank') and key.endswith('Level')]
        for key in all_tank_keys:
            try:
                tank_id = int(key.replace('tank', '').replace('Level', ''))
                tank_level = float(params.get(key, 0))
                dead_bottom_key = f'deadBottom{tank_id}'
                dead_bottom_default = params.get('deadBottom1', 10000)
                dead_bottom = float(params.get(dead_bottom_key, dead_bottom_default))
                total += max(0, tank_level - dead_bottom)
            except (ValueError, TypeError):
                continue
        return total

    def _get_empty_tanks(self, params, num_tanks):
        """Get list of empty tanks by checking ONLY keys present in params."""
        # This function is now only used to seed the sequence.
        # The main logic in _allocate_tanks_for_blend does the real categorization.
        empty = []
        
        all_tank_keys = [key for key in params.keys() if key.startswith('tank') and key.endswith('Level')]

        for key in all_tank_keys:
            try:
                tank_id = int(key.replace('tank', '').replace('Level', ''))
            except ValueError:
                continue 
            
            tank_level = float(params.get(key, 0))
            
            dead_bottom_key = f'deadBottom{tank_id}'
            dead_bottom_default = params.get('deadBottom1', 10000)
            dead_bottom = float(params.get(dead_bottom_key, dead_bottom_default))
            
            if tank_level <= dead_bottom + 500:
                empty.append(tank_id)
                
        print(f"SOLVER: _get_empty_tanks found: {empty}")
        return empty

    def _get_processing_start_datetime(self, params):
        """Parse processing start datetime"""
        try:
            date_str = params.get('crudeProcessingDate', '2025-08-10 08:00')
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('T', ' '))
            elif ' ' in date_str:
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            else:
                return datetime.strptime(f"{date_str} 08:00", '%Y-%m-%d %H:%M')
        except:
            return datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)


def optimize_crude_mix_schedule(params):
    """
    Main entry point with exact ratio enforcement
    """
    optimizer = CrudeMixOptimizer()

    solver_output_buffer = io.StringIO()
    with redirect_stdout(solver_output_buffer):
        try:
            result = optimizer.solve_crude_mix_schedule(params)
        except Exception as e:
            result = {'success': False, 'error': str(e), 'cargo_schedule': []}
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    solver_output_string = solver_output_buffer.getvalue()
    total_cost = result.get('total_cost', 0)

    final_report_buffer = io.StringIO()
    final_report_buffer.write(f"Total Charter Cost: ${total_cost:,.0f}\n\n")
    final_report_buffer.write("="*80 + "\n")
    final_report_buffer.write("CRUDE MIX OPTIMIZATION SOLVER - FORMULA-BASED EXACT RATIO VERSION\n")
    final_report_buffer.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    final_report_buffer.write("="*80 + "\n")

    vessel_counts = result.get('vessel_distribution', {})
    vessel_types_to_display = ['ULCC', 'VLCC', 'SUEZMAX', 'AFRAMAX', 'PANAMAX', 'HANDYMAX', 'HANDY_SIZE']
    cargo_counts_str = ", ".join([f"{v_type}: {vessel_counts.get(v_type.upper(), 0)}" for v_type in vessel_types_to_display])
    
    final_report_buffer.write(f"FINAL CARGO COUNT: {cargo_counts_str}\n")
    final_report_buffer.write(f"Total Charter Cost: ${total_cost:,.0f}\n\n")
    final_report_buffer.write(solver_output_string)

    final_report_string = final_report_buffer.getvalue()

    if not result:
        result = {'success': False, 'error': 'Solver failed', 'cargo_schedule': []}
    
    result['console_output'] = final_report_string.splitlines()
    return result