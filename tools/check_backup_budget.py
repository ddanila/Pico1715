#!/usr/bin/env python3
"""Conservative constant-current reserve envelope and ideal-clamp charging model."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def budget(p):
 c=p['cell_capacitance_f']*p['capacitance_min_factor']*p['aged_capacitance_factor']/2
 r=2*p['cell_initial_esr_ohm']*p['aged_esr_factor']+p['fuse_wiring_assumed_ohm']
 tol=p['resistor_tolerance'];ref=p['reference_v'];allow=p['offset_bound_assumed_v']+p['hysteresis_allowance_assumed_v']
 low=(ref*(1-p['reference_error_assumed_fraction'])-allow)*(1+p['ready_top_ohm']*(1-tol)/(p['sense_bottom_ohm']*(1+tol)))
 high=(ref*(1+p['reference_error_assumed_fraction'])+allow)*(1+p['ready_top_ohm']*(1+tol)/(p['sense_bottom_ohm']*(1-tol)))
 rows=[]
 for load in p['load_examples_a']:
  floor=p['required_vsys_assumed_v']+p['discharge_diode_bound_v']+load*r
  seconds=max(0,c*(low-floor)/load)
  blocks=max(0,min(1600,math.floor((seconds-p['isolation_margin_assumed_s'])/p['journal_block_time_example_s'])))
  rows.append(dict(load_a=load,minimum_bank_v=round(floor,4),reserve_s=round(seconds,4),example_dirty_limit=blocks,can_admit_first_sector=blocks>=2))
 rmin=p['charge_resistance_ohm']*(1-tol)
 return dict(effective_aged_capacitance_f=c,aged_series_resistance_ohm=r,ready_threshold_envelope_v=[low,high],max_startup_charge_a=p['input_max_v']/rmin,max_charge_resistor_w=p['input_max_v']**2/rmin,rows=rows)
def charge(p,clamp=True):
 # Mismatched aged/new cells, ideal ceiling: explicitly NOT a TL431 transient model.
 caps=[6.3,13.0];v=[0.,0.];peak=[0.,0.];ready=None;dt=.1
 for tick in range(72000):
  current=max(0,(p['input_max_v']-.1-sum(v))/99)
  for i in range(2):
   dv=(current-v[i]/p['balance_resistance_ohm']-50e-6)/caps[i]*dt
   v[i]=max(0,v[i]+dv)
   if clamp:v[i]=min(v[i],2.55)
   peak[i]=max(peak[i],v[i])
  if ready is None and sum(v)>=p['reference_v']*(1+p['ready_top_ohm']/p['sense_bottom_ohm']):ready=tick*dt
 return dict(ideal_cell_clamps=clamp,cell_capacitance_f=caps,maximum_cell_v=peak,after_7200s_cell_v=v,time_to_nominal_ready_s=ready)
def main():
 source=ROOT/'hardware/backup-power/budget-inputs.json';p=json.loads(source.read_text());r=budget(p)
 assert not p['qualified'] and r['max_startup_charge_a']<.06 and r['max_charge_resistor_w']<1
 report=dict(schema=1,hardware_executed=False,protected_writeback_qualified=False,budget=r,charge_cases=[charge(p),charge(p,False)],limits=['Constant-current LDO model, not measured SD burst load or SPICE.','Ideal clamps do not establish TL431 stability, overshoot or thermal behavior.','Example block times MUST NOT be copied into protected firmware settings.','READY threshold alone does not prove capacitor presence, capacitance or health; a controlled load test and measured reserve budget are mandatory.'],source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [source,Path(__file__)]})
 (ROOT/'reports/backup-budget.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
