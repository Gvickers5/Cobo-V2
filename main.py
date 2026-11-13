import os
from bootstrap_cobo import bootstrap_environment

# 1. Run the setup check silently
bootstrap_environment()

# 2. After folders are confirmed, launch the actual app
import manager
