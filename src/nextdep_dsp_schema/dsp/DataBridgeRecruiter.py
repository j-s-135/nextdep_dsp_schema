import os
import sys
import argparse
import json
from typing import Optional
from mmcif.api.PdbxContainers import DataContainer
from mmcif.api.DataCategory import DataCategory
from nextdep_dsp_schema.io.MarshalUtil import MarshalUtil
from ..config.ConfigUtil import ConfigUtil
from ..define.ContentDefinition import ContentDefinition
from ..define.DictionaryApiProviderWrapper import DictionaryApiProviderWrapper


def guess_file_type(filename:str) -> Optional[str]:
    """
    Guess the file type based on the extension of the given filename.

    Args:
        filename:

    Returns:
        filetype: cif, json, or None
    """
    ext = os.path.splitext(os.path.basename(filename.lower()))
    ext = ext[1].lstrip(".")
    if ext in ["mmcif", "cif"]:
        return "cif"
    elif ext in ["json"]:
        return "json"
    else:
        return None

def getUnitCardinalityCategories(schemafile, cache) -> list:

    configPath = schemafile
    cachePath = cache

    defaultConfigName = "site_info_configuration"
    mockTopPath = None
    cfgOb = ConfigUtil(configPath=configPath, defaultSectionName=defaultConfigName, mockTopPath=mockTopPath)

    schemaGroupName = "pdbx_mmcif"
    configName = cfgOb.getDefaultSectionName()

    contentDefHelper = cfgOb.getHelper("CONTENT_DEF_HELPER_MODULE", sectionName=configName, cfgOb=cfgOb)
    cardD = contentDefHelper.getCardinalityKeyItem(schemaGroupName)

    dP = DictionaryApiProviderWrapper(cachePath, cfgOb=cfgOb, configName=configName, useCache=True)
    dictApi = dP.getApiByName(schemaGroupName)
    contentInfo = ContentDefinition(dictApi, contentDefHelper=contentDefHelper, schemaGroupName=schemaGroupName)

    unitCardinalityList = contentInfo.getUnitCardinalityList([cardD])

    return unitCardinalityList

class DataBridgeRecruiter:

    def __init__(self, infile:str, outfile:str, unit_cardinality:bool=True, workpath:str="/tmp", schemafile:str=None, cache:str=None, **kwargs):
        """
        Attributes:
            infile (str): cif or json file path
            outfile (str): cif or json file path
            unit_cardinality (bool): allows loops of one object to be represented as a single object
            workpath (str): working directory path passed to MarshalUtil
        """
        self.workpath = workpath
        if not os.path.exists(infile):
            sys.exit("error - file %s does not exist" % infile)
        self.infile = infile
        self.outfile = outfile
        # find name for data block
        inlabel = os.path.splitext(os.path.basename(infile).upper())[0].split("-")[0]
        outlabel = os.path.splitext(os.path.basename(outfile).upper())[0].split("-")[0]
        # assert inlabel == outlabel, "input and output filenames must be the same %s %s" % (inlabel, outlabel)
        # render loops of one object as a single object
        self.unit_cardinality = unit_cardinality
        self.schemafile = schemafile
        self.cache = cache
        if self.unit_cardinality:
            if self.schemafile and self.cache:
                if not os.path.exists(self.schemafile):
                    sys.exit("error - schema file %s does not exist" % self.schemafile)
                if not os.path.exists(self.cache):
                    sys.exit("error - cache path %s does not exist" % self.cache)
                self.unit_cardinality_list = getUnitCardinalityCategories(self.schemafile, self.cache)
                print("unit cardinality list %s" % self.unit_cardinality_list)
            else:
                sys.exit("unit cardinality requires schema file and cache path")

    def get_entry_id(self):
        """get the entry id from the input file name"""
        return os.path.splitext(os.path.basename(self.infile))[0].lower().split("-")[0]

    def format_outfile_path(self, outfile: str, datablocks: int) -> str:
        """expand file names for datablocks > 1
        args:
            outfile (str): output file path
            datablocks (int): number of datablocks found
        returns:
            str: output file path
        """
        datablock = datablocks - 1
        outfilename = os.path.basename(outfile)
        outfilename = os.path.splitext(outfilename)[0] + "-" + str(datablock) + os.path.splitext(outfilename)[1]
        outfilepath = os.path.join(os.path.dirname(outfile), outfilename)
        return outfilepath

    def getJson(self):
        """
        Converts mmCIF data to JSON format for one or multiple data blocks.
        Each data block is converted to a separate JSON file indexed with -[index].cif.
        """

        mu = MarshalUtil(workpath=self.workpath)

        """
        [DataContainer1, DataContainer2, ...]
        """
        dcs = mu.doImport(self.infile, fmt="mmcif")

        print("marshaling returned %d containers" % len(dcs))

        for x in range(len(dcs)):

            item = dcs[x]

            """
            DataContainer
            {category1: DataCategory1, category2: DataCategory2, ...}
            """
            c = item.getObjCatalog()

            j = {}

            for k, v in c.items():

                """
                DataCategory
                category:str, attrs:list, data:list[list]
                """
                dc = c[k]

                if isinstance(dc, DataCategory):
                    name, attrs, data = dc.get()
                    if name not in j:
                        shortname = name
                        if name.startswith("_"):
                            shortname = name[1:]
                        if len(data) == 1 and self.unit_cardinality and shortname in self.unit_cardinality_list:
                            j[name] = {}
                            row = data[0]
                            for attr, val in zip(attrs, row):
                                j[name][attr] = val
                        else:
                            j[name] = []
                            for row in data:
                                rowD = {}
                                for attr, val in zip(attrs, row):
                                    rowD[attr] = val
                                j[name].append(rowD)
                    else:
                        sys.exit("duplicate category name %s" % name)
                else:
                    sys.exit("unexpected data type %s" % type(dc))

            if len(dcs) > 1:
                fp = self.format_outfile_path(self.outfile, x + 1)
            else:
                fp = self.outfile

            if os.path.exists(fp):
                os.remove(fp)
                print("removed duplicate file: %s" % fp)

            with open(fp, "w") as f:
                json.dump(j, f, indent=2)

            print("wrote %s" % fp)

        print("marshaling complete")

    def getPdbx(self):
        """Converts JSON data to PDBx/mmCIF format for one data block."""

        mu = MarshalUtil(workpath=self.workpath)

        """
        OrderedDict(category: [ OrderedDict(attr:val) ] | category: OrderedDict(attr:val))
        """
        ordc = mu.doImport(self.infile, fmt="json")

        obj = DataContainer(self.get_entry_id())

        for k,v in ordc.items():
            name = k
            if isinstance(v, list):
                attrs = list(v[0].keys())
                data = [list(vv.values()) for vv in v]
            else:
                attrs = list(v.keys())
                data = [list(v.values())]
            dc = DataCategory(name, attributeNameList=attrs, rowList=data)
            obj.append(dc)

        mu.doExport(self.outfile, [obj], fmt="mmcif-dict")

        print("wrote %s" % self.outfile)

        print("marshaling complete")

def recruitDataBridge(infile:str, outfile:str, unit_cardinality:bool=False, workpath:str="/tmp", schemafile:str | None = None, cachePath:str | None = None) -> bool:
    dbn = DataBridgeRecruiter(infile, outfile, unit_cardinality=unit_cardinality, workpath=workpath, schemafile=schemafile, cache=cachePath)
    if guess_file_type(infile) == "cif" and guess_file_type(outfile) == "json":
        dbn.getJson()
    elif guess_file_type(infile) == "json" and guess_file_type(outfile) == "cif":
        dbn.getPdbx()
    else:
        print("error guessing file type: %s = %s, %s = %s" % (infile, guess_file_type(infile), outfile, guess_file_type(outfile)))
        return False
    return True

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", required=True, help="cif file")
    parser.add_argument("--outfile", required=True, help="json file")
    parser.add_argument("--unit_cardinality", action="store_true", help="retain unit cardinality")
    parser.add_argument("--workpath", default="/tmp", help="working path")
    parser.add_argument("--schemafile", default=None, help="schema file")
    parser.add_argument("--cache", default=None, help="schema cache directory path")

    args = parser.parse_args()
    infile = args.infile
    outfile = args.outfile
    unit_cardinality = False
    if args.unit_cardinality:
        unit_cardinality = True
    schemafile = None
    if args.schemafile:
        schemafile = args.schemafile
    cachePath = None
    if args.cache:
        cachePath = args.cache

    result = dataBridge(infile, outfile, unit_cardinality, args.workpath, schemafile, cachePath)
    if result:
        print("completed")
    else:
        print("failed")
