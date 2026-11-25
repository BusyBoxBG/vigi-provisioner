import itertools
import unittest
from vigi_provisioner.vigi_label_scan import parse_label_stream

QR = "TP11326062CFD849E902020"
MAC = "1869459F31F7"
SERIAL = "22630K7001456"

class LabelScanTests(unittest.TestCase):
    def test_joined_codes_any_order_and_duplicates(self):
        for parts in itertools.permutations((QR, MAC, SERIAL)):
            for suffix in ("", QR, MAC, SERIAL, QR+MAC+SERIAL):
                raw="".join(parts)+suffix
                with self.subTest(raw=raw):
                    result=parse_label_stream(raw)
                    self.assertTrue(result["ready"],result)
                    self.assertEqual(result["fields"],dict(device_id="1326062CFD849E902",mac_address=MAC,label_serial=SERIAL.lower()))

    def test_separators_and_lowercase_input(self):
        for separator in ("\r", "\n", "\t", "|", " "):
            self.assertTrue(parse_label_stream(separator.join((QR,MAC,SERIAL)).lower()+separator)["ready"])

    def test_partial_input_never_ready(self):
        for length in range(len(QR+MAC+SERIAL)):
            self.assertFalse(parse_label_stream((QR+MAC+SERIAL)[:length])["ready"])
        self.assertFalse(parse_label_stream(QR+MAC+SERIAL+"TP1")["ready"])

    def test_conflicting_camera_values_block_acceptance(self):
        for extra in ("TP1CB7516E6763362E22040", "C03A5555BA40", "22630K7001457"):
            result=parse_label_stream(QR+MAC+SERIAL+extra)
            self.assertFalse(result["ready"],result)

    def test_numeric_serial_and_mac_ambiguity_is_not_guessed(self):
        result=parse_label_stream(QR+"1234567890123123456789012")
        self.assertFalse(result["ready"])
        self.assertTrue(parse_label_stream(QR+"|1234567890123|123456789012|")["ready"])

    def test_c340s_and_c540s_wrapper(self):
        result=parse_label_stream("TP13B27D0E00114896A204030689353CD67224A3Q2000438")
        self.assertTrue(result["ready"],result)
        self.assertEqual(result["fields"]["label_serial"],"224a3q2000438")

    def test_unrecognized_input_and_limits(self):
        self.assertFalse(parse_label_stream(QR+MAC+SERIAL+"!")["ready"])
        self.assertFalse(parse_label_stream("TP11326062CFD849E902999")["ready"])
        for raw in (None,"X"*4097):
            with self.assertRaises(ValueError):parse_label_stream(raw)

class DiscoveryCrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.fields=parse_label_stream(QR+MAC+SERIAL)["fields"]
        self.camera=dict(ip="192.168.0.60",mac="18-69-45-9f-31-f7",model="VIGI C320I",factory_flag=0,serial=QR,onvif_endpoint="http://192.168.0.60:80/onvif/device_service")

    def test_matching_pair_and_identical_repeats(self):
        from vigi_provisioner.vigi_label_scan import crosscheck_discovery
        result=crosscheck_discovery(self.fields,[self.camera,dict(self.camera)])
        self.assertTrue(result["matched"])
        self.assertEqual(result["camera"]["model"],"VIGI C320I")
        self.assertNotIn("label_serial",result["camera"])

    def test_identity_conflicts(self):
        from vigi_provisioner.vigi_label_scan import crosscheck_discovery
        for changed in (dict(mac="c0-3a-55-55-ba-40"),dict(serial="TP1CB7516E6763362E22040"),dict(ip="192.168.0.61"),dict(model="VIGI C540S")):
            self.assertFalse(crosscheck_discovery(self.fields,[self.camera,dict(self.camera,**changed)])["matched"])

    def test_missing_uninitialized_or_device_id_not_confirmed(self):
        from vigi_provisioner.vigi_label_scan import crosscheck_discovery
        for cameras in ([],[dict(self.camera,factory_flag=1)],[dict(self.camera,serial=None)]):
            self.assertFalse(crosscheck_discovery(self.fields,cameras)["matched"])

    def test_unrelated_camera_different_ip_does_not_prevent_match(self):
        from vigi_provisioner.vigi_label_scan import crosscheck_discovery
        other=dict(self.camera,mac="c0-3a-55-55-ba-40",serial="TP1CB7516E6763362E22040",ip="192.168.0.61")
        self.assertTrue(crosscheck_discovery(self.fields,[self.camera,other])["matched"])
