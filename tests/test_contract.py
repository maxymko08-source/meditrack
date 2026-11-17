"""Cross-check actual CAD manifest, firmware constants and HTTP event sequence."""
import hashlib
import json
from pathlib import Path
import re
import unittest
from tests import test_backend as fixtures

ROOT=Path(__file__).resolve().parents[1]
class ContractTests(unittest.TestCase):
    def test_eight_steps_and_supervised_return(self):
        fixture=fixtures.BackendTests(methodName='runTest');fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        design=json.loads((ROOT/'meditrack/3d_model/mechanism.json').read_text())
        header=(ROOT/'firmware/MediTrack/mechanism.h').read_text()
        angles=[int(n) for n in re.search(r'ANGLES\[8\] = \{([^}]+)',header)[1].split(',')]
        self.assertEqual(angles,design['compartment_angles_deg'])
        self.assertEqual(design['source_sha256'],hashlib.sha256((ROOT/'meditrack/3d_model/design.py').read_bytes()).hexdigest())
        _,plan=fixture.load()
        for i,angle in enumerate(angles):
            fixture.due(plan,i)
            command=fixture.client.get('/api/check',headers=fixture.headers).get_json()
            self.assertEqual((command['compartment'],command['previous_compartment'],command['angle']),(i+1,i,angle))
            fixture.client.post('/api/confirm',headers=fixture.headers,json={'event_id':command['event_id'],'outcome':'command_completed'})
        self.assertEqual(fixture.store.poll('device-a')['mode'],'exhausted')
        home=fixture.store.request_home(101,'device-a')
        self.assertEqual(home['angle'],design['home_angle_deg'])
        fixture.store.confirm('device-a',home['event_id'],'homed')
        new=fixture.store.prepare_refill(101,'device-a')
        fixture.store.refill(101,'device-a',new['plan_id'])
        self.assertEqual(fixture.store.status(101,'device-a')['position'],0)

    def test_no_future_compartment_opens_during_forward_step(self):
        # Two 16-degree sectors overlap only when their centres are <16 degrees apart.
        for target in range(1,9):
            for tenth in range((target-1)*200,target*200+1):
                angle=tenth/10
                for future in range(target+1,9):
                    self.assertGreaterEqual(abs(future*20-angle),20)

if __name__=='__main__':unittest.main()
