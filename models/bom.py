# =============================================================================
# RESEMIS EPM ENGINE - BOM MODULE
# =============================================================================
# Bill of Materials (BOM) data structures and loading.
# BOM defines the inputs required to produce each kg of output product.
#
# KEY CONSTRAINT: SUM(qty_per_kg) >= 1 to account for yield loss
# =============================================================================

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class BOMInput:
    """Single input in a product's BOM."""
    input_id: str
    input_name: str
    qty_per_kg: float  # kg of input per kg of output product
    input_type: str  # raw_material | additive | energy | packaging | labor


@dataclass
class ProductBOM:
    """Complete BOM for a single product."""
    product_id: str
    inputs: List[BOMInput]

    def total_input_qty(self) -> float:
        """Sum of all input quantities (should be >= 1 for yield loss)."""
        return sum(inp.qty_per_kg for inp in self.inputs)

    def get_input(self, input_id: str) -> BOMInput:
        """Get specific input by ID."""
        for inp in self.inputs:
            if inp.input_id == input_id:
                return inp
        raise KeyError(f"Input {input_id} not found in BOM for {self.product_id}")


def load_bom(assumptions: Dict) -> Dict[str, ProductBOM]:
    """
    Load BOM definitions from assumptions.

    Args:
        assumptions: Full assumptions dictionary with 'bom' section

    Returns:
        Dict mapping product_id to ProductBOM

    Expected structure in assumptions:
        bom:
          by_product:
            <product_id>:
              inputs:
                - input_id: str
                  input_name: str
                  qty_per_kg: float
                  input_type: str
    """
    result: Dict[str, ProductBOM] = {}

    bom_config = assumptions.get("bom", {})
    by_product = bom_config.get("by_product", {})

    for product_id, product_data in by_product.items():
        inputs_list = product_data.get("inputs", [])

        bom_inputs = []
        for input_data in inputs_list:
            bom_input = BOMInput(
                input_id=input_data.get("input_id", ""),
                input_name=input_data.get("input_name", ""),
                qty_per_kg=input_data.get("qty_per_kg", 0.0),
                input_type=input_data.get("input_type", "raw_material")
            )
            bom_inputs.append(bom_input)

        result[product_id] = ProductBOM(
            product_id=product_id,
            inputs=bom_inputs
        )

    return result


def validate_bom(bom: Dict[str, ProductBOM]) -> List[str]:
    """
    Validate BOM completeness and constraints.

    Args:
        bom: Dict mapping product_id to ProductBOM

    Returns:
        List of validation errors (empty if valid)

    Validations:
        - Every product has >= 1 input
        - All qty_per_kg >= 0
        - SUM(qty_per_kg) >= 1 (yield loss requirement)
    """
    errors = []

    for product_id, product_bom in bom.items():
        # Check has at least one input
        if len(product_bom.inputs) == 0:
            errors.append(f"Product {product_id} has no inputs in BOM")
            continue

        # Check all quantities are non-negative
        for inp in product_bom.inputs:
            if inp.qty_per_kg < 0:
                errors.append(
                    f"Negative qty_per_kg for {product_id}/{inp.input_id}: "
                    f"{inp.qty_per_kg}"
                )

        # Check yield loss (total >= 1)
        total_qty = product_bom.total_input_qty()
        if total_qty < 1.0:
            errors.append(
                f"BOM for {product_id} has total qty {total_qty:.4f} < 1.0 "
                f"(violates yield loss constraint)"
            )

    return errors


def get_all_input_ids(bom: Dict[str, ProductBOM]) -> List[str]:
    """
    Get all unique input IDs across all products.

    Args:
        bom: Dict mapping product_id to ProductBOM

    Returns:
        List of unique input IDs
    """
    input_ids = set()
    for product_bom in bom.values():
        for inp in product_bom.inputs:
            input_ids.add(inp.input_id)
    return sorted(list(input_ids))


# =============================================================================
# END OF BOM MODULE
# =============================================================================
