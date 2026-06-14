from power.cell import cell
from copy import deepcopy


class cell_static(cell):

    def __init__(self, cell_def, model="RSeriesModel", diode_type="open"):
        super().__init__(cell_type=None, model=model, diode_type=diode_type, localCellFile=False, localDiodeFile=False)
        self.cell_def = cell_def
        self.type = "static"

    def prepareModel(self):

        model  = deepcopy(self.model)
        config = deepcopy(self.config)

        isc = self.cell_def["isc"]
        imp = self.cell_def["imp"]
        vmp = self.cell_def["vmp"]
        voc = self.cell_def["voc"]

        config["r_interconnect"] = self.cell_def["r_interconnect"]

        return model, config, isc, imp, vmp, voc
