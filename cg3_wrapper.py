import subprocess
import os
import argparse


class CG3Error(Exception):
    """Exception for CG3 subprocess errors"""
    pass

class CG3Wrapper:
    """
    A wrapper class for the various CG3 command-line tools

    The default names assume that the binaries (cg3, cg-conv, etc.) are in PATH
    """
    def __init__(self, 
                 cg3_path="vislcg3",
                 cg_conv_path="cg-conv",
                 cg_comp_path="cg-comp",
                 cg_proc_path="cg-proc",
                 cg_strictify_path="cg-strictify",
                 extra_env=None):
        self.cg3_path = cg3_path
        self.cg_conv_path = cg_conv_path
        self.cg_comp_path = cg_comp_path
        self.cg_proc_path = cg_proc_path
        self.cg_strictify_path = cg_strictify_path

        # Merge any extra environment variables (e.g. CG3_DEFAULT) into os.environ
        self.extra_env = extra_env if extra_env is not None else {}

    def _build_env(self):
        env = os.environ.copy()
        env.update(self.extra_env)
        return env

    def _run_process(self, command, input_text=None):
        """
        Runs command as a subprocess
        Raises CG3Error if exits with nonzero code
        Returns a tuple (stdout, stderr)
        """
        env = self._build_env()
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
        except FileNotFoundError as e:
            raise CG3Error(f"Command not found: {command[0]}") from e

        stdout, stderr = process.communicate(input=input_text)
        if process.returncode != 0:
            raise CG3Error(
                f"Command {' '.join(command)} failed with return code {process.returncode}\n"
                f"stderr: {stderr}"
            )
        return stdout, stderr

    def run_vislcg3(self, grammar_file, input_text, options=None):
        """
        Runs the primary cg3 binary (vislcg3) with the specified grammar file and input.
        Options should be a list of extra command-line arguments
        Options can include flags such as -p, --in-cg, --out-plain, etc. 
        See https://edu.visl.dk/cg3/single/#cmdreference for more info on valid arguments
        """
        command = [self.cg3_path, "-g", grammar_file]
        if options:
            command.extend(options)
        command.extend(["-g", grammar_file])
        return self._run_process(command, input_text=input_text)

    def run_cg_conv(self, input_text, options=None):
        """
        Runs cg-conv to convert between stream formats.
        Options can include flags such as -p, --in-cg, --out-plain, etc.
        """
        command = [self.cg_conv_path]
        if options:
            command.extend(options)
        return self._run_process(command, input_text=input_text)

    def run_cg_comp(self, grammar_file, output_file):
        """
        Runs cg-comp to compile a grammar from text to binary form. 
        Requires grammars to be in UTF-8 encoding.
        No options to include, only compiles grammars to binary.
        """
        command = [self.cg_comp_path, grammar_file, output_file]
        return self._run_process(command)

    def run_cg_proc(self, grammar_file, input_text, options=None):
        """
        Runs cg-proc for grammar application on an input stream.
        Options can include flags such as -t, -s, -r, etc.
        """
        command = [self.cg_proc_path]
        if options:
            command.extend(options)
        command.append(grammar_file)
        return self._run_process(command, input_text=input_text)

    def run_cg_strictify(self, grammar_file, options=None):
        """
        Runs cg-strictify on a grammar file. 
        Options can include flags such as --strip, --secondary, --regex, etc.
        """
        command = [self.cg_strictify_path]
        if options:
            command.extend(options)
        command.append(grammar_file)
        return self._run_process(command)

def main():
    parser = argparse.ArgumentParser(
        description="CG3 Wrapper: Run CG3 tools with grammar and input files."
    )
    parser.add_argument("--tool", required=True, choices=["vislcg3", "cg-conv", "cg-comp", "cg-proc", "cg-strictify"],
                        help="Specify which CG3 tool to run.")
    parser.add_argument("--grammar", help="Path to the grammar file (required for vislcg3, cg-proc, and cg-strictify).")
    parser.add_argument("--input", help="Path to the input text file (required for vislcg3, cg-conv, and cg-proc).")
    parser.add_argument("--output", help="Optional: Path to write the output (for cg-comp).")
    parser.add_argument("--cg3-options", nargs=argparse.REMAINDER, default=[],
                        help="Optional: Additional command-line options for CG3 tools.")
    
    args = parser.parse_args()

    # Initialize the wrapper
    # If needed, add environment variables (CG3_DEFAULT, etc.) to extra_env.
    cg3 = CG3Wrapper(extra_env={
        # for example "CG3_DEFAULT": "--verbose"
    })

    # Added integration for the main tools, code messy right now, should be more modular
    try:
        if args.tool == "vislcg3":
            if not args.grammar or not args.input:
                print("Error: --grammar and --input are required for vislcg3.")
                return
            with open(args.input, "r", encoding="utf-8") as f:
                input_text = f.read()
            output, error = cg3.run_vislcg3(args.grammar, input_text, args.cg3_options)

        elif args.tool == "cg-conv":
            if not args.input:
                print("Error: --input is required for cg-conv.")
                return
            with open(args.input, "r", encoding="utf-8") as f:
                input_text = f.read()
            output, error = cg3.run_cg_conv(input_text, args.cg3_options)

        elif args.tool == "cg-comp":
            if not args.grammar or not args.output:
                print("Error: --grammar and --output are required for cg-comp.")
                return
            output, error = cg3.run_cg_comp(args.grammar, args.output)

        elif args.tool == "cg-proc":
            if not args.grammar or not args.input:
                print("Error: --grammar and --input are required for cg-proc.")
                return
            with open(args.input, "r", encoding="utf-8") as f:
                input_text = f.read()
            output, error = cg3.run_cg_proc(args.grammar, input_text, args.cg3_options)

        elif args.tool == "cg-strictify":
            if not args.grammar:
                print("Error: --grammar is required for cg-strictify.")
                return
            output, error = cg3.run_cg_strictify(args.grammar, args.cg3_options)


        # Write to output file if specified, otherwise print to stdout
        if args.output and args.tool != "cg-comp":
            with open(args.output, "w", encoding="utf-8") as outf:
                outf.write(output)
            print(f"Output written to {args.output}")
        else:
            print("Output:\n", output)


        if error:
            print("Error Output:\n", error)
    except CG3Error as e:
        print("An error occurred while running CG3:")
        print(e)

if __name__ == "__main__":
    main()
