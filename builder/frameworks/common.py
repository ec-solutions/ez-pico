# WizIO 2022 Georgi Angelov
#   http://www.wizio.eu/
#   https://github.com/Wiz-IO/wizio-pico

from distutils.log import error
import os
from os.path import join
from shutil import copyfile
from colorama import Fore
from pico import *
from uf2conv import dev_uploader
from SCons.Script import Builder

bynary_type_info = []

def do_copy(src, dst, name):
    file_name = join(dst, name)
    if False == os.path.isfile( file_name ):
        copyfile( join(src, name), file_name )
    return file_name

def do_mkdir(path, name):
    dir = join(path, name)
    if False == os.path.isdir( dir ):
        try:
            os.mkdir(dir)
        except OSError:
            print ("[ERROR] Creation of the directory %s failed" % dir)
            exit(1)
    return dir

def ini_file(env): # add defaut keys
    ini = join( env.subst("$PROJECT_DIR"), 'platformio.ini' )
    f = open(ini, "r")
    txt = f.read()
    f.close()
    f = open(ini, "a+")
    if 'monitor_port'  not in txt: f.write("\n;monitor_port = SELECT SERIAL PORT\n")
    if 'monitor_speed' not in txt: f.write(";monitor_speed = 115200\n")    
    if 'lib_deps'      not in txt: f.write("\n;lib_deps = \n")
    if True == env.wifi:
        if 'build_flags' not in txt: f.write("\n;build_flags = \n")
    else:
        if 'build_flags' not in txt: f.write("\nbuild_flags = -D PICO_CYW43_ARCH_POLL ; select wifi driver mode\n")
    f.close()

def dev_create_template(env):
    ini_file(env)
    src = join(env.PioPlatform().get_package_dir("framework-wizio-pico"), "templates")
    dst = do_mkdir( env.subst("$PROJECT_DIR"), "include" )
    do_copy(src, dst, "tusb_config.h")

    if "freertos" in env.GetProjectOption("lib_deps", []) or "USE_FREERTOS" in env.get("CPPDEFINES"):
        do_copy(src, dst, "FreeRTOSConfig.h")

    if "VFS" in env.GetProjectOption("lib_deps", []) or "USE_VFS" in env.get("CPPDEFINES"):
        do_copy(src, dst, "vfs_config.h")

    if 'APPLICATION'== env.get("PROGNAME"):
        if "fatfs" in env.GetProjectOption("lib_deps", []):
            do_copy(src, dst, "ffconf.h")

        dst = do_mkdir( env.subst("$PROJECT_DIR"), join("include", "pico") )
        autogen_filename = join(dst, "config_autogen.h")
        if False == os.path.isfile( autogen_filename ):
            default_board = "pico.h"
            autogen_board = env.BoardConfig().get("build.autogen_board", default_board )
            f = open(autogen_filename, "w")
            f.write("/* SELECT OTHER BOARD */\n")
            f.write('#include "boards/{}"\n'.format(autogen_board))
            f.close()

        dst = join(env.subst("$PROJECT_DIR"), "src")
        if False == os.path.isfile( join(dst, "main.cpp") ):
            do_copy(src, dst, "main.c" )

    if 'BOOT-2'== env.get("PROGNAME"):
        dst = do_mkdir( env.subst("$PROJECT_DIR"), join("include", "pico") )
        do_copy(src, dst, "config_autogen.h" )

def dev_nano(env):
    enable_nano = env.BoardConfig().get("build.nano", "enable") # no <sys/lock>
    nano = []
    if enable_nano == "enable":
        nano = ["-specs=nano.specs", "-u", "_printf_float", "-u", "_scanf_float" ]
    if len(nano) > 0: print('  * SPECS        :', nano[0][7:])
    else:             print('  * SPECS        : default')
    return nano

def dev_compiler(env, application_name = 'APPLICATION'):
    env["FRAMEWORK_DIR"] = env.framework_dir
    env.sdk = env.BoardConfig().get("build.sdk", "SDK") # get/set default SDK
    env.variant = env.BoardConfig().get("build.variant", 'raspberry-pi-pico')
    env.wifi = env.BoardConfig().get("build.WIFI", False )
    print()
    print( Fore.BLUE + "%s RASPBERRYPI PI PICO RP2040 ( PICO - %s )" % (env.platform.upper(), env.sdk.upper()) )
    env.Replace(
        BUILD_DIR = env.subst("$BUILD_DIR").replace("\\", "/"),
        AR="arm-none-eabi-ar",
        AS="arm-none-eabi-as",
        CC="arm-none-eabi-gcc",
        GDB="arm-none-eabi-gdb",
        CXX="arm-none-eabi-g++",
        OBJCOPY="arm-none-eabi-objcopy",
        RANLIB="arm-none-eabi-ranlib",
        SIZETOOL="arm-none-eabi-size",
        ARFLAGS=["rc"],
        SIZEPROGREGEXP=r"^(?:\.text|\.data|\.boot2|\.rodata)\s+(\d+).*",
        SIZEDATAREGEXP=r"^(?:\.data|\.bss|\.ram_vector_table)\s+(\d+).*",
        SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
        SIZEPRINTCMD='$SIZETOOL --mcu=$BOARD_MCU -C -d $SOURCES',
        PROGSUFFIX=".elf",
        PROGNAME = application_name
    )
    cortex = ["-march=armv6-m", "-mcpu=cortex-m0plus", "-mthumb"]
    env.heap_size = env.BoardConfig().get("build.heap", "2048")
    optimization = env.BoardConfig().get("build.optimization", "-Os")
    stack_size = env.BoardConfig().get("build.stack", "2048")
    print('  * OPTIMIZATION :', optimization)
    if 'ARDUINO' == env.get("PROGNAME"):
        if "freertos" in env.GetProjectOption("lib_deps", []) or "USE_FREERTOS" in env.get("CPPDEFINES"):
            pass
        else:
            print('  * STACK        :', stack_size)
            print('  * HEAP         : maximum')
    else:
        print('  * STACK        :', stack_size)
        print('  * HEAP         :', env.heap_size)
    #fix_old_new_stdio(env)
    env.Append(
        ASFLAGS=[ cortex, "-x", "assembler-with-cpp" ],
        CPPPATH = [
            join("$PROJECT_DIR", "src"),
            join("$PROJECT_DIR", "lib"),
            join("$PROJECT_DIR", "include"),
            join( env.framework_dir, "wizio", "pico"),
            join( env.framework_dir, "wizio", "newlib"),
            join( env.framework_dir, env.sdk, "include"),
            join( env.framework_dir, env.sdk, "cmsis", "include"), #
        ],
        CPPDEFINES = [
            "NDEBUG",
            "PICO_ON_DEVICE=1",
            "PICO_HEAP_SIZE="  + env.heap_size,
            "PICO_STACK_SIZE=" + stack_size,
        ],
        CCFLAGS = [
            cortex,
            optimization,
            "-fdata-sections",
            "-ffunction-sections",
            "-Wall",
            "-Wextra",
            "-Wfatal-errors",
            "-Wno-sign-compare",
            "-Wno-type-limits",
            "-Wno-unused-parameter",
            "-Wno-unused-function",
            "-Wno-unused-but-set-variable",
            "-Wno-unused-variable",
            "-Wno-unused-value",
            "-Wno-strict-aliasing",
            "-Wno-maybe-uninitialized"
        ],
        CFLAGS = [
            cortex,
            "-Wno-discarded-qualifiers",
            "-Wno-ignored-qualifiers",
            "-Wno-attributes", #
        ],
        CXXFLAGS = [
            "-fno-rtti",
            "-fno-exceptions",
            "-fno-threadsafe-statics",
            "-fno-non-call-exceptions",
            "-fno-use-cxa-atexit",
        ],
        LINKFLAGS = [
            cortex,
            optimization,
            "-nostartfiles",
            "-Xlinker", "--gc-sections",
            "-Wl,--gc-sections",
            "--entry=_entry_point",
            dev_nano(env)
        ],
        LIBSOURCE_DIRS = [ join(env.framework_dir, "library"),  ],
        LIBPATH        = [ join(env.framework_dir, "library"), join("$PROJECT_DIR", "lib") ],
        LIBS           = ['m', 'gcc'],
        BUILDERS = dict(
            ElfToBin = Builder(
                action = env.VerboseAction(" ".join([
                    "$OBJCOPY", "-O",  "binary",
                    "$SOURCES", "$TARGET",
                ]), "Building $TARGET"),
                suffix = ".bin"
            )
        ),
        UPLOADCMD = dev_uploader
    )
    if False == env.wifi:
        env.Append( CPPDEFINES = [ "PICO_WIFI" ] )    

def add_libraries(env): # is PIO LIB-s
    if "freertos" in env.GetProjectOption("lib_deps", []) or "USE_FREERTOS" in env.get("CPPDEFINES"):
        env.Append(  CPPPATH = [ join( env.framework_dir, "library", "freertos", "include" ), ]  )
        print('  * RTOS         : FreeRTOS')
        if "USE_FREERTOS" not in env.get("CPPDEFINES"):
            env.Append(  CPPDEFINES = [ "USE_FREERTOS"] )

    if "cmsis-dap" in env.GetProjectOption("lib_deps", []):
        env.Append( CPPDEFINES = [ "DAP" ], )

def add_boot(env):
    boot = env.BoardConfig().get("build.boot", "w25q080") # get boot
    if "w25q080" != boot and "$PROJECT_DIR" in boot:
        boot = boot.replace('$PROJECT_DIR', env["PROJECT_DIR"]).replace("\\", "/")
    bynary_type_info.append(boot)
    env.BuildSources( join("$BUILD_DIR", env.platform, "wizio", "boot"), join(env.framework_dir, "boot", boot) )

def add_bynary_type(env):
    add_boot(env)
    bynary_type = env.BoardConfig().get("build.bynary_type", 'default')
    env.address = env.BoardConfig().get("build.address", "empty")
    linker      = env.BoardConfig().get("build.linker", "empty")
    if "empty" != linker and "$PROJECT_DIR" in linker:
        linker = linker.replace('$PROJECT_DIR', env["PROJECT_DIR"]).replace("\\", "/")
    if 'copy_to_ram' == bynary_type:
        if "empty" == env.address: env.address = '0x10000000'
        if "empty" == linker: linker = 'memmap_copy_to_ram.ld'
        env.Append(  CPPDEFINES = ['PICO_COPY_TO_RAM'] )
    elif 'no_flash' == bynary_type:
        if "empty" == env.address: env.address = '0x20000000'
        if "empty" == linker: linker = 'memmap_no_flash.ld'
        env.Append(  CPPDEFINES = ['PICO_NO_FLASH'] )
    elif 'blocked_ram' == bynary_type:
        print('TODO: blocked_ram is not supported yet')
        exit(0)
        if "empty" == env.address: env.address = ''
        if "empty" == linker: linker = ''
        env.Append( CPPDEFINES = ['PICO_USE_BLOCKED_RAM'] )
    else: #default
        if "empty" == env.address: env.address = '0x10000000'
        if "empty" == linker: linker = 'memmap_default.ld'
    env.Append( LDSCRIPT_PATH = join(env.framework_dir, env.sdk, "pico", "pico_standard_link", linker) )
    bynary_type_info.append(linker)
    bynary_type_info.append(env.address)
    print('  * BINARY TYPE  :' , bynary_type, bynary_type_info  )
    add_libraries(env)

def dev_finalize(env):
# WIZIO
    env.BuildSources( join("$BUILD_DIR", env.platform, "wizio"), join(env.framework_dir, "wizio") )
# SDK
    add_bynary_type(env)
    add_sdk(env)
    env.Append(LIBS = env.libs)
    dev_add_modules(env)
    print()

def dev_config_board(env):
    src = join(env.PioPlatform().get_package_dir("framework-wizio-pico"), "templates")
    dst = do_mkdir( env.subst("$PROJECT_DIR"), "include" )

    if False == env.wifi:
        print("  * WIFI         : NO")
        return
    ### pico w board
    else:
        do_copy(src, dst, "lwipopts.h") # for user edit

        env.Append(
            CPPDEFINES = [ "PICO_W", 'CYW43_SPI_PIO', 'CYW43_USE_SPI' ],
            CPPPATH = [
                join( env.framework_dir, env.sdk, "lib", "lwip", "src", "include" ),
                join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "src" ),
                join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "firmware" ),
            ],            
        )

        ### pico wifi support
        env.BuildSources( 
            join( "$BUILD_DIR", "wifi", "pico" ), 
            join(env.framework_dir, env.sdk), 
            [ "-<*>", "+<pico/pico_cyw43_arch>", "+<pico/pico_lwip>", ]
        )

        ### wifi spi driver & firmware
        env.BuildSources( 
            join( "$BUILD_DIR", "wifi" , "cyw43-driver" ), 
            join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "src" ), 
            [ "+<*>", "-<cyw43_sdio.c>", ] # remove sdio driver  
        )

        ### LWIP: for add other files, use PRE:SCRIPT.PY
        env.BuildSources( 
            join( "$BUILD_DIR", env.platform, "lwip", "api" ),
            join( env.framework_dir, env.sdk, "lib", "lwip", "src", "api" ), 
        )
        env.BuildSources( 
            join( "$BUILD_DIR", env.platform, "lwip", "core" ),
            join( env.framework_dir, env.sdk, "lib", "lwip", "src", "core" ), 
            [ "+<*>",  "-<ipv6>", ] # remove ipv6
        )
        env.BuildSources( 
            join( "$BUILD_DIR", env.platform, "lwip", "netif" ),
            join( env.framework_dir, env.sdk, "lib", "lwip", "src", "netif" ), 
            [ "-<*>", "+<ethernet.c>", ]
        )        

        ### wifi firmware object
        """
        BUILD_DIR = env.subst( "$BUILD_DIR" )
        do_mkdir( BUILD_DIR, "wifi" )
        do_mkdir( join( BUILD_DIR, "wifi" ), "firmware" )
        WIFI_FIRMWARE_DIR = join( BUILD_DIR, "wifi", "firmware" )
        WIFI_FIRMWARE_OBJ = join( WIFI_FIRMWARE_DIR, "wifi_firmware.o" ) 
        WIFI_FIRMWARE_BIN = join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "firmware", "43439A0-7.95.49.00.combined" )
        old_name = WIFI_FIRMWARE_BIN
        old_name = '_binary_' + old_name.replace('\\', '_').replace('/', '_').replace('.', '_').replace(':', '_').replace('-', '_')
        cmd = [ "$OBJCOPY", "-I", "binary", "-O", "elf32-littlearm", "-B", "arm", "--readonly-text",
                "--rename-section", ".data=.big_const,contents,alloc,load,readonly,data",
                "--redefine-sym", old_name + "_start=fw_43439A0_7_95_49_00_start",
                "--redefine-sym", old_name + "_end=fw_43439A0_7_95_49_00_end",
                "--redefine-sym", old_name + "_size=fw_43439A0_7_95_49_00_size",
                WIFI_FIRMWARE_BIN, # SOURCE BIN
                WIFI_FIRMWARE_OBJ  # TARGET OBJ
        ]
        env.AddPreAction( 
                join( "$BUILD_DIR", "wifi" , "cyw43-driver", "cyw43_bus_pio_spi.o" ), # TRIGER
                env.VerboseAction(" ".join(cmd), "Compiling wifi/firmware/wifi_firmware.o") 
        )       
        print( "  * WIFI         : Compile Firmware Object" )
        env.Append( LINKFLAGS = [ WIFI_FIRMWARE_OBJ ] )
        return
        """
        ### use pre-compiled wifi_firmware.o
        print( "  * WIFI         : Firmware Object" )
        env.Append( LINKFLAGS = [ join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "src", "wifi_firmware.o" ) ] ) 
        return
        ### use pre-compiled libwifi_firmware.a
        print( "  * WIFI         : Firmware Library" )
        env.Append( # AS LIB
            LIBPATH = [ join( env.framework_dir, env.sdk, "lib", "cyw43-driver", "src" ) ], 
            LIBS = ['wifi_firmware'] 
        )
        
# EXPERIMENTAL FEATURE: LOAD MODULES

'''
### Add & Compile not compiled sources with main builder

###[INI] custom_modules = 
    $PROJECT_DIR/modules/MODULE_SCRYPT.py = parameters if need
    $PROJECT_DIR/any_folder_with_py_scripts

### example: MODULE_VERNO.py
from os.path import join
def module_init(env, parameter=''): # if parameter: string separated by space
    name = "verno"
    print( "  *", name.upper() ) # just info
    path = join( env.framework_dir, "sdk", "middleware", name)
    env.Append( CPPPATH = [ join( path, "inc" ) ] )    
    env.BuildSources( join( "$BUILD_DIR", "modules", name ), join( path, "src" ) )
'''

from importlib.machinery import SourceFileLoader

# private 
def dev_load_module(filename, params, env):
    name = 'module_' +  str( abs(hash( filename )) )
    m = SourceFileLoader(name, filename).load_module() 
    m.module_init( env, params )     

# public: call it at builder end
def dev_add_modules(env): 
    #lines = env.BoardConfig().get("build.modules", "0")
    lines = env.GetProjectOption("custom_modules", "0")
    if '0' != lines: 
        print("Project Modules:")  
        for line in lines.split("\n"):
            if line == '': continue
            ### Cleaning the INI line
            line = line.strip().replace("\r", "").replace("\t", "")
            delim = '='  # for parameters
            params = ''  # from ini line
            if delim in line:
                params = line[ line.index( delim ) + 1 : ].strip()  # remove delim and whitespaces
                params = " ".join( params.split() )                 # remove double spaces, params are separated by a space   
                line = line.partition( delim )[0].strip()           # remove delim and whitespaces
            module_path = env.subst( line ).strip().replace("\\", "/")
            ### Loading
            if False == os.path.exists(module_path):
                print("[ERROR] MODULE PATH NOT EXIST: %s" % module_path)
                exit(0)
            if True == os.path.isdir( module_path ):  # files in folder
                for root, dirs, files in os.walk( module_path ):                       
                    files = [ f for f in files if f.endswith(".py") ] # filter py files
                    for file in files: 
                        dev_load_module( join(root, file), params, env)
            else: # single file
                dev_load_module( module_path, params, env)
   
