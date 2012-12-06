# LIBTBX_SET_DISPATCHER_NAME mmtbx.analyze_peptides

from __future__ import division
import sys
from mmtbx.validation import analyze_peptides

if __name__ == "__main__":
  analyze_peptides.run(args=sys.argv[1:])

