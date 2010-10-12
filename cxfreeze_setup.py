from cx_Freeze import setup, Executable

setup (
    name = "Sauce RC",
    executables = [Executable("saucerc.py"), Executable("sauceserver.py")]
)
