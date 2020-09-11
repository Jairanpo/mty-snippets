import subprocess
import sgtk
import pprint



# Initialize the logger so we get output to our terminal.
sgtk.LogManager().initialize_custom_handler()

# Set debugging to true so that we get
# more verbose output, (should only be used for testing).
sgtk.LogManager().global_debug = True


# Instantiate the authenticator object.
authenticator = sgtk.authentication.ShotgunAuthenticator()

# Optionally you can clear any previously cached sessions. 
# This will force you to enter credentials each time.
authenticator.clear_default_user()

# The user will be prompted for their username,
# password, and optional 2-factor authentication code. 
# If a QApplication is available, a UI will pop-up. 
# If not, the credentials will be prompted
# on the command line. 
# The user object returned encapsulates the login information.
user = authenticator.get_user()

# Tells Toolkit which user to use for connecting to Shotgun. 
# Note that this should
# always take place before creating an `Sgtk` instance.
sgtk.set_authenticated_user(user)

mgr = sgtk.bootstrap.ToolkitManager()

mgr.base_configuration = \
    "sgtk:descriptor:dev?" + \
        "mac_path=/Users/jairanpo/Projects/MIGHTY/mty-config-default&" + \
            "windows_path=C:\Development\Mighty\mty-config-default"

mgr.plugin_id = "basic.shell"

project = {"type": "Project", "id": 124}

def pre_engine_start_callback(ctx):
    '''
    Called before the engine is started.

    :param :class:"~sgtk.Context" ctx: Context into
        which the engine will be launched. This can also be used
        to access the Toolkit instance.
    '''
    ctx.sgtk.synchronize_filesystem_structure()

mgr.pre_engine_start_callback = pre_engine_start_callback

engine = mgr.bootstrap_engine("tk-shell", entity=project)

pprint.pprint(engine.commands.keys())