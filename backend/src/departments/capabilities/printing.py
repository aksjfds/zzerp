from departments.contracts import CAP_SPECIAL_PRINTING


class SpecialPrintingCapability:
    def printing_profile(self) -> dict[str, str]:
        self.require_capability(CAP_SPECIAL_PRINTING)
        return {
            "template": f"{self.descriptor.code}_work_order",
            "department_code": self.descriptor.code,
        }
