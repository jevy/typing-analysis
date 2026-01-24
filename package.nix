{ lib
, python3Packages
, fetchFromGitHub ? null
}:

python3Packages.buildPythonApplication rec {
  pname = "typing-analysis";
  version = "0.1.0";
  format = "pyproject";

  # For local development, use current directory
  # For production, replace with fetchFromGitHub or similar
  src = ./.;

  nativeBuildInputs = [
    python3Packages.setuptools
  ];

  propagatedBuildInputs = [
    python3Packages.evdev
  ];

  nativeCheckInputs = [
    python3Packages.pytestCheckHook
  ];

  meta = {
    description = "Keystroke capture and analysis for improving typing skills";
    homepage = "https://github.com/jevin/typing-analysis";
    license = lib.licenses.mit;
    maintainers = [];
    mainProgram = "typing-report";
  };
}
