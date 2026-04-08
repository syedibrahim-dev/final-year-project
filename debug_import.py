import sys
sys.path.append('.')

import traceback
try:
    from routes import inventory
    print("Importing routes.inventory succeeded!")
except Exception as e:
    print("FAILED TO IMPORT routes.inventory")
    traceback.print_exc()

import main
print("main.py loaded. Check the output above to see if inventory routes were imported.")
