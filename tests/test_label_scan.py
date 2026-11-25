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
