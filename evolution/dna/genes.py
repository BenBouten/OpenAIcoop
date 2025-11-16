"""Genetic blueprint definitions for body modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, MutableMapping, Optional

__all__ = [
    "ModuleGene",
    "GenomeConstraints",
    "Genome",
    "ensure_genome",
]


@dataclass(frozen=True)
class ModuleGene:
    """Description of a body module within a DNA blueprint."""

    gene_id: str
    module_type: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    parent: Optional[str] = None
    slot: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Serialise the gene into a JSON-friendly mapping."""

        data: Dict[str, object] = {
            "module_type": self.module_type,
            "parameters": dict(self.parameters),
        }
        if self.parent:
            data["parent"] = self.parent
        if self.slot:
            data["slot"] = self.slot
        return data

    @classmethod
    def from_mapping(cls, gene_id: str, data: Mapping[str, object]) -> "ModuleGene":
        """Build a gene from raw mapping data."""

        if "module_type" not in data:
            raise ValueError(f"Gene '{gene_id}' is missing the 'module_type' attribute")
        module_type = str(data["module_type"]).strip()
        if not module_type:
            raise ValueError(f"Gene '{gene_id}' requires a non-empty module type")
        parameters_raw = data.get("parameters", {})
        parameters: Mapping[str, object]
        if isinstance(parameters_raw, Mapping):
            parameters = dict(parameters_raw)
        else:
            parameters = {"value": parameters_raw}
        parent_value = data.get("parent")
        parent = str(parent_value) if parent_value not in (None, "") else None
        slot_value = data.get("slot")
        slot = str(slot_value) if slot_value not in (None, "") else None
        if parent and not slot:
            raise ValueError(
                f"Gene '{gene_id}' attaches to '{parent}' but no slot was provided"
            )
        return cls(
            gene_id=str(gene_id),
            module_type=module_type,
            parameters=parameters,
            parent=parent,
            slot=slot,
        )


@dataclass(frozen=True)
class GenomeConstraints:
    """Global constraints a genome must satisfy."""

    max_mass: float = 120.0
    nerve_capacity: float = 12.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "max_mass": float(self.max_mass),
            "nerve_capacity": float(self.nerve_capacity),
        }

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, object]]) -> "GenomeConstraints":
        if not data:
            return cls()
        return cls(
            max_mass=float(data.get("max_mass", cls.max_mass)),
            nerve_capacity=float(data.get("nerve_capacity", cls.nerve_capacity)),
        )


@dataclass(frozen=True)
class Genome:
    """DNA blueprint composed of module genes."""

    genes: Mapping[str, ModuleGene]
    constraints: GenomeConstraints = field(default_factory=GenomeConstraints)

    def to_dict(self) -> Dict[str, object]:
        return {
            "constraints": self.constraints.to_dict(),
            "modules": {gene_id: gene.to_dict() for gene_id, gene in self.genes.items()},
        }

    def validate_structure(self) -> None:
        """Sanity check ordering and ensure a single root exists."""

        self.root_gene()
        self.ordered_genes()

    def ordered_genes(self) -> List[ModuleGene]:
        """Return genes sorted so that parents appear before their children."""

        pending: MutableMapping[str, ModuleGene] = dict(self.genes)
        ordered: List[ModuleGene] = []
        resolved: set[str] = set()
        while pending:
            progress = False
            for gene_id, gene in list(pending.items()):
                if gene.parent is None or gene.parent in resolved:
                    ordered.append(gene)
                    resolved.add(gene_id)
                    del pending[gene_id]
                    progress = True
            if not progress:
                unresolved = ", ".join(sorted(pending))
                raise ValueError(
                    "Unable to order genes; check for missing parents or cycles: " + unresolved
                )
        return ordered

    def root_gene(self) -> ModuleGene:
        """Return the single root gene without a parent."""

        roots = [gene for gene in self.genes.values() if gene.parent is None]
        if not roots:
            raise ValueError("Genome does not define a root module")
        if len(roots) > 1:
            raise ValueError("Genome defines multiple root modules")
        return roots[0]


def ensure_genome(data: Mapping[str, object]) -> Genome:
    """Normalise raw mapping data into a :class:`Genome` instance."""

    modules_raw = data.get("modules") or data.get("genes")
    if not isinstance(modules_raw, Mapping) or not modules_raw:
        raise ValueError("DNA blueprint requires at least one module definition")

    genes: Dict[str, ModuleGene] = {}
    for gene_id, gene_data in modules_raw.items():
        if not isinstance(gene_data, Mapping):
            raise TypeError(f"Gene '{gene_id}' must be a mapping")
        gene = ModuleGene.from_mapping(str(gene_id), gene_data)
        genes[gene.gene_id] = gene

    constraints = GenomeConstraints.from_mapping(
        data.get("constraints") if isinstance(data.get("constraints"), Mapping) else None
    )
    genome = Genome(genes=genes, constraints=constraints)
    # Validate structure early to provide fast feedback.
    genome.validate_structure()
    return genome
