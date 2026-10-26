# SPDX-License-Identifier: MIT
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from firmware_costs import stress_profile, stress_environment, validate_stress

class StressProfileTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(stress_profile({})['width'],0)
        self.assertNotIn('PICO1715_STRESS_SD_SEQUENCE',stress_environment({}))
    def test_reject_invalid(self):
        for bad in ({'unknown':1},{'period':0},{'period':True},{'width':258},
                    {'phase':257},{'extra_us':[0]*5},{'extra_us':[0]*5+[True]},
                    {'sd_delays_us':[-1]},{'sd_delays_us':[0]*17},{'index_phase_us':100001}):
            with self.subTest(bad=bad),self.assertRaises(ValueError): stress_profile(bad)
    def test_schedule_accounting(self):
        for phase in range(7):
            p=stress_profile(dict(period=7,width=3,phase=phase,extra_us=[1]*6,
                                  sd_delays_us=[20000,200,5000],index_phase_us=-64))
            calls=[0,1,2,7,17,101]
            stats=dict(config=p,hits=[sum((i+phase)%7<3 for i in range(n)) for n in calls],
                       sd_calls=2,sd_min_us=200,sd_max_us=20000,index_resets=1,index_start_tick=491443)
            validate_stress(stats,calls)
            stats['hits'][0]+=1
            with self.assertRaises(ValueError):validate_stress(stats,calls)
