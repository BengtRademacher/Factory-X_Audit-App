import unittest
import pandas as pd
import numpy as np
from core.data_parser import DataParser
from io import BytesIO

class TestCoreModules(unittest.TestCase):
    
    def test_data_parser_metrics(self):
        # Mock DataFrame
        df = pd.DataFrame({
            "elapsedTime": [0, 10, 20],
            "Power1": [100, 200, 100],
            "Power2": [50, 50, 50]
        })
        
        details, summary = DataParser.compute_metrics(df, ["Power1", "Power2"])
        
        self.assertIn("Power1", details)
        self.assertEqual(details["Power1"]["mean"], 133.33)
        self.assertEqual(summary["max"], 250.0)
        
    def test_duty_cycle(self):
        df = pd.DataFrame({
            "Power1": [0, 100, 100, 0, 100]
        })
        # Mean is 60, threshold 0.1 * 60 = 6. Active if > 6.
        # 3 out of 5 samples are active = 60%
        cycle = DataParser.calculate_duty_cycle(df, ["Power1"], 60)
        self.assertEqual(cycle, 60.0)

if __name__ == "__main__":
    unittest.main()

