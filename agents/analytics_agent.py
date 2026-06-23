# agents/analytics_agent.py

import pandas as pd
import plotly.express as px
from typing import Dict, Any, List
from agents import logger

class AnalyticsAgent:
    """
    Agent 6: Analytics Agent (Production-Grade)
    Processes cumulative operational metrics and historical incident data using Pandas and Plotly
    to output metrics, frequencies, recommendations, and dashboard-ready charts.
    """

    def __init__(self):
        """Initializes the agent."""
        self.name = "AnalyticsAgent"

    def run(self, historical_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entry point for executing analytics aggregations.

        Args:
            historical_incidents: List of dicts representing previously processed shipping incident workflows.

        Returns:
            A validated dict containing dashboard-ready metrics and Plotly figures:
            {
                "most_common_issue_types": List[str],
                "average_delivery_delay_days": float,
                "resolution_success_rate": float,
                "issue_frequencies": Dict[str, int],
                "business_recommendations": List[str],
                "top_root_causes": List[str],
                "plotly_issues_json": str, (JSON dictionary of Plotly pie figure)
                "plotly_carriers_json": str, (JSON dictionary of Plotly bar figure)
                # Legacy keys for backwards-compatibility:
                "total_incidents_processed": int,
                "sla_compliance_rate": float,
                "average_resolution_cost": float,
                "issue_distribution": Dict[str, float],
                "carrier_performance": Dict[str, Any]
            }
        """
        logger.info(f"[{self.name}] Initiating analytics compilation over {len(historical_incidents)} incidents.")

        # Guard clause: Return default safe stats if history list is empty
        if not historical_incidents:
            logger.warning(f"[{self.name}] No historical incident data available to aggregate.")
            return self._empty_stats()

        try:
            # 1. Load data into Pandas DataFrame
            df = self._load_dataframe(historical_incidents)

            # 2. Compute Core KPIs
            total_incidents = len(df)
            avg_delay = float(df["delay_days"].mean())
            success_rate = float(1.0 - df["sla_breached"].mean())
            avg_cost = float(df["cost"].mean())

            # 3. Compute Frequencies and Distributions
            issue_counts = df["category"].value_counts().to_dict()
            most_common_issues = list(df["category"].value_counts().index)
            top_causes = list(df["root_cause"].value_counts().index)
            
            issue_dist = {k: float(round(v / total_incidents, 2)) for k, v in issue_counts.items()}

            # 4. Compute Carrier Performance metrics
            carrier_perf = {}
            if "carrier" in df.columns:
                carrier_groups = df.groupby("carrier")
                for carrier_name, group in carrier_groups:
                    group_total = len(group)
                    group_breached = group["sla_breached"].sum()
                    carrier_perf[str(carrier_name)] = {
                        "sla_rate": float(round(1.0 - (group_breached / group_total), 2)),
                        "avg_delay_hours": float(round(group["delay_days"].mean() * 24.0, 1)),
                        "total_shipments": int(group_total)
                    }

            # 5. Generate dynamic Business Recommendations
            recommendations = self._generate_recommendations(df, most_common_issues, top_causes)

            # 6. Generate Plotly dashboard-ready JSON figures
            issues_fig_json = self._generate_issues_pie_chart(df)
            carriers_fig_json = self._generate_carriers_bar_chart(df)

            return {
                "most_common_issue_types": most_common_issues,
                "average_delivery_delay_days": float(round(avg_delay, 2)),
                "resolution_success_rate": float(round(success_rate, 2)),
                "issue_frequencies": issue_counts,
                "business_recommendations": recommendations,
                "top_root_causes": top_causes,
                "plotly_issues_json": issues_fig_json,
                "plotly_carriers_json": carriers_fig_json,
                "total_incidents_processed": total_incidents,
                "sla_compliance_rate": float(round(success_rate, 2)),
                "average_resolution_cost": float(round(avg_cost, 2)),
                "issue_distribution": issue_dist,
                "carrier_performance": carrier_perf
            }

        except Exception as e:
            logger.error(f"[{self.name}] Analytics compilation failed: {e}. Defaulting to safe fallback.")
            return self._empty_stats()

    def _load_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Parses and flat maps incident JSON structures into a Pandas DataFrame."""
        flat_records = []
        for r in data:
            classification = r.get("classification") or {}
            root_cause = r.get("root_cause") or {}
            delay = r.get("delay_prediction") or {}
            resolution = r.get("resolution") or {}
            route = r.get("route_info") or {}

            # Flat dictionary mapping
            record = {
                "shipment_id": r.get("shipment_id"),
                "category": classification.get("category", "Courier issue"),
                "severity": classification.get("severity", "MEDIUM"),
                "root_cause": root_cause.get("root_cause", "CARRIER_OPERATIONAL"),
                "delay_days": delay.get("estimated_delay_days") or (delay.get("predicted_delay_hours", 48.0) / 24.0),
                "cost": resolution.get("resolution_cost", 0.0),
                "sla_breached": resolution.get("sla_breach_risk", False),
                "carrier": route.get("carrier", "Unknown")
            }
            flat_records.append(record)

        return pd.DataFrame(flat_records)

    def _generate_recommendations(self, df: pd.DataFrame, common_issues: List[str], top_causes: List[str]) -> List[str]:
        """Generates dynamic operational recommendations based on statistical parameters."""
        recs = [
            "Maintain regional warehouse stock allocation schedules based on demand profiles to prevent dispatch backlogs."
        ]

        if not top_causes:
            return recs

        primary_cause = top_causes[0]
        if primary_cause == "WEATHER_DISRUPTION":
            recs.append("Weather delays represent a major logistical bottleneck. We recommend activating dynamic rerouting rules to bypass impacted airports and ground lanes.")
        elif primary_cause == "CUSTOMS_HOLD":
            recs.append("Customs clearance is causing delay holds. Coordinate automated commercial invoice submission checks with global carrier partners.")
        elif primary_cause == "LOST_IN_TRANSIT":
            recs.append("High lost-in-transit rates detected. Implement cargo tagging and GPS tracker checks on shipments valued above $150.")
        elif primary_cause == "INCORRECT_ADDRESS":
            recs.append("Address metadata discrepancies are forcing final-mile holds. Integrate address validation API at checkout to prevent courier routing failures.")

        # Check for carrier SLA issues
        if "carrier" in df.columns and "sla_breached" in df.columns:
            carrier_sla = df.groupby("carrier")["sla_breached"].mean()
            poor_carriers = carrier_sla[carrier_sla > 0.15].index.tolist()
            if poor_carriers:
                recs.append(f"Carrier accounts ({', '.join(poor_carriers)}) breached the 15% SLA threshold. Initiate service level reviews or shift load allocation.")

        # Check for category-specific issues
        if "category" in df.columns:
            website_freq = (df["category"] == "Website issue").mean()
            if website_freq > 0.10:
                recs.append("Website checkout portal data sync errors are causing delivery delays. Schedule engineering logs database audits.")

        return recs

    def _generate_issues_pie_chart(self, df: pd.DataFrame) -> str:
        """Generates a Plotly pie chart of issues and outputs it as serialized JSON."""
        try:
            fig = px.pie(
                df,
                names="category",
                title="Issue Categories Distribution",
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Blues
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f1f5f9'),
                margin=dict(t=30, b=10, l=10, r=10)
            )
            # Serialize to JSON dictionary
            return fig.to_json()
        except Exception as e:
            logger.error(f"Failed to generate Plotly issue chart: {e}")
            return "{}"

    def _generate_carriers_bar_chart(self, df: pd.DataFrame) -> str:
        """Generates a Plotly grouped bar chart of carrier stats and outputs it as serialized JSON."""
        try:
            if "carrier" not in df.columns or df.empty:
                return "{}"
            
            # Aggregate stats using pandas
            carrier_stats = df.groupby("carrier").agg(
                sla_compliance=("sla_breached", lambda x: float(round((1.0 - x.mean()) * 100, 1))),
                avg_delay=("delay_days", lambda x: float(round(x.mean() * 24.0, 1)))
            ).reset_index()

            # Melt to long format for Plotly grouped bar chart
            melted_df = pd.melt(
                carrier_stats,
                id_vars=["carrier"],
                value_vars=["sla_compliance", "avg_delay"],
                var_name="Metric",
                value_name="Value"
            )

            fig = px.bar(
                melted_df,
                x="carrier",
                y="Value",
                color="Metric",
                barmode="group",
                title="Carrier Performance Metrics",
                color_discrete_map={"sla_compliance": "#6366f1", "avg_delay": "#fbbf24"}
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f1f5f9'),
                margin=dict(t=30, b=10, l=10, r=10),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)')
            )
            return fig.to_json()
        except Exception as e:
            logger.error(f"Failed to generate Plotly carrier chart: {e}")
            return "{}"

    def _empty_stats(self) -> Dict[str, Any]:
        """Provides default safe analytics structures when data holds empty lists."""
        return {
            "most_common_issue_types": [],
            "average_delivery_delay_days": 0.0,
            "resolution_success_rate": 1.0,
            "issue_frequencies": {},
            "business_recommendations": [
                "Aggregate shipping tickets to activate operational recommendation reports."
            ],
            "top_root_causes": [],
            "plotly_issues_json": "{}",
            "plotly_carriers_json": "{}",
            "total_incidents_processed": 0,
            "sla_compliance_rate": 1.0,
            "average_resolution_cost": 0.0,
            "issue_distribution": {},
            "carrier_performance": {}
        }

