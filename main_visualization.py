"""Lanceur simple pour tester la visualisation interactive du graphe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from cesipath.graph_generator import GraphGenerator
from cesipath.models import GraphGenerationConfig
from cesipath.visualization import GraphVisualizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualisation interactive d'un graphe CESIPATH.")
    parser.add_argument("--nodes", type=int, default=30, help="Nombre de sommets.")
    parser.add_argument("--seed", type=int, default=42, help="Seed de generation.")
    parser.add_argument("--sigma", type=float, default=0.18, help="Sigma de la dynamique gaussienne.")
    parser.add_argument(
        "--mean-reversion",
        type=float,
        default=0.35,
        help="Force de retour du cout dynamique vers le cout statique.",
    )
    parser.add_argument(
        "--max-multiplier",
        type=float,
        default=1.80,
        help="Multiplicateur maximal applique au cout statique pour borner le cout dynamique.",
    )
    parser.add_argument(
        "--forbid-prob",
        type=float,
        default=0.03,
        help="Probabilite qu'une arete active devienne temporairement indisponible.",
    )
    parser.add_argument(
        "--restore-prob",
        type=float,
        default=0.20,
        help="Probabilite qu'une arete indisponible redevienne active.",
    )
    parser.add_argument(
        "--max-disabled-ratio",
        type=float,
        default=0.20,
        help="Part maximale d'aretes dynamiques simultanement indisponibles.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = GraphGenerationConfig(
        node_count=args.nodes,
        seed=args.seed,
        auto_density_profile=True,
        dynamic_sigma=args.sigma,
        dynamic_mean_reversion_strength=args.mean_reversion,
        dynamic_max_multiplier=args.max_multiplier,
        dynamic_forbid_probability=args.forbid_prob,
        dynamic_restore_probability=args.restore_prob,
        dynamic_max_disabled_ratio=args.max_disabled_ratio,
    )

    generator = GraphGenerator(config)
    instance = generator.generate()
    visualizer = GraphVisualizer(instance, generator)

    print("Instance generee :")
    for key, value in instance.summary().items():
        print(f"- {key}: {value}")

    visualizer.show_dynamic_graph()
    plt.show()


if __name__ == "__main__":
    main()
