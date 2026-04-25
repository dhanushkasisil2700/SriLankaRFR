import duckdb
import pandas as pd
from typing import List, Tuple
from datetime import datetime
import os

class CurveStore:
    def __init__(self, db_path: str = "data/lankarfr.duckdb"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with duckdb.connect(self.db_path) as con:
            # We recreate if it lacks the method column
            try:
                con.execute("SELECT method FROM curve_points LIMIT 1")
            except duckdb.BinderException:
                # Column doesn't exist, we must recreate
                con.execute("DROP TABLE IF EXISTS curve_points")
                
            con.execute("""
                CREATE TABLE IF NOT EXISTS curve_points (
                    date DATE,
                    tenor DOUBLE,
                    zero_rate DOUBLE,
                    method VARCHAR,
                    PRIMARY KEY (date, tenor, method)
                )
            """)
            
    def save_curve(self, date_str: str, points: List[Tuple[float, float]], method: str = 'linear_exact'):
        """
        Save curve points for a given date and method.
        date_str: YYYY-MM-DD
        points: List of (tenor, zero_rate)
        method: curve Generation method (e.g., 'linear_exact', 'nelson_siegel')
        """
        # Parse date to ensure format
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        df = pd.DataFrame(points, columns=['tenor', 'zero_rate'])
        df['date'] = dt
        df['method'] = method
        
        with duckdb.connect(self.db_path) as con:
            # Upsert
            con.execute("BEGIN TRANSACTION")
            con.execute("""
                DELETE FROM curve_points WHERE date = ? AND method = ?
            """, [dt, method])
            con.execute("INSERT INTO curve_points SELECT date, tenor, zero_rate, method FROM df")
            con.execute("COMMIT")
            
    def get_curve(self, date_str: str, method: str = 'linear_exact') -> List[Tuple[float, float]]:
        """
        Retrieve curve points for a given date.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        with duckdb.connect(self.db_path) as con:
            result = con.execute("""
                SELECT tenor, zero_rate 
                FROM curve_points 
                WHERE date = ? AND method = ?
                ORDER BY tenor
            """, [dt, method]).fetchall()
            
        return result
        
    def get_methods_for_date(self, date_str: str) -> List[str]:
        """
        Get all curve methodology names available for a specific date.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        with duckdb.connect(self.db_path) as con:
            result = con.execute("""
                SELECT DISTINCT method 
                FROM curve_points 
                WHERE date = ?
            """, [dt]).fetchall()
            
        return [r[0] for r in result]

    def get_all_dates(self) -> List[str]:
        """
        Retrieve all unique dates present in the store as strings.
        """
        with duckdb.connect(self.db_path) as con:
            result = con.execute("""
                SELECT DISTINCT date 
                FROM curve_points 
                ORDER BY date DESC
            """).fetchall()
            
        return [r[0].strftime("%Y-%m-%d") for r in result]
