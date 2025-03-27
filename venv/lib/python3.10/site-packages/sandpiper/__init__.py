import io
import os
import shutil
import sys
import zipfile
import click
from pathlib import Path

import requests
from io import BytesIO
import argparse


class get_sphelp(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Create an empty context
        zip_buffer = io.BytesIO()
        zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False)
        try:
            resp = requests.post(
                "https://faas.makerchip.com/function/sandpiper-faas",
                files=(
                    ('args',
                     (None, "--help", "--no-color")),
                    ('context', ('context.zip', zip_buffer.getvalue())),
                ),
                stream=True
            )
        except:
            print("Error while accessing the compile service.")
            sys.exit(1)

        # We can close the zip buffer.
        zip_buffer.close()

        # Open response zip.
        try:
            z = zipfile.ZipFile(BytesIO(resp.content))
        except:
            print("Error while extracting response.")

        # Print stderr, stdout
        stderr = z.open('stderr').read().decode('utf-8')
        stdout = z.open('stdout').read().decode('utf-8')

        sys.stderr.write(stderr)
        sys.stdout.write(stdout)
        parser.exit()


def run():
    # ToS check and prompt
    home = Path.home()
    file = "%s/.makerchip_accepted" % home
    if not Path(file).exists():
        if click.confirm('Please review our Terms of Service: https://makerchip.com/terms/.\n'
                         'Have you read and do you accept these Terms of Service?', default=False):
            Path(file).touch()
        else:
            print("ToS must be accepted!")
            sys.exit(1)
    Path(file).touch()
    print("You have agreed to our Terms of Service here: https://makerchip.com/terms.")

    parser = argparse.ArgumentParser(description="SandPiper-SaaS",
                                     epilog="SandPiper-SaaS Edition runs the SandPiper(TM) TL-Verilog processor as a microservice in the cloud to support "
                                            "easy open-source development. "
                                            "To display the SandPiper help, use --sphelp.")
    parser.register('action', 'sphelp', get_sphelp)
    parser.add_argument('-i', type=str, help="Top-level TLV file.", required=True)
    parser.add_argument('-f', type=str, help="Include files.", nargs='+')
    parser.add_argument('-o', help="SystemVerilog output filename: *.sv.", type=str)
    parser.add_argument('--endpoint', help="Compile service endpoint.", type=str)
    parser.add_argument('--sphelp', help="SandPiper help.", nargs=0, action='sphelp')
    parser.add_argument('--outdir', help="Output directory.", type=str)
    parser.add_argument('--sv_url_inc', help="Return the sv_url_inc directory with the response. The folder contains the files pulled by the URL include macros.", action='store_true')
    parser.add_argument('--default_includes',
                        help="Get default include files.",
                        action='store_true')
    #parser.add_argument('sandpiper_args', type=str, nargs='*', help='Arguments to be passed to SandPiper. (See sandpiper-saas --sphelp)')
    args, unknown = parser.parse_known_args()

    top = args.i
    additional_args = ' '.join([str(elem) for elem in unknown])
    #sandpiper_args = ' '.join([str(elem) for elem in args.sandpiper_args])
    include_files = args.f
    tlv_output = args.o
    if tlv_output is not None:
        tlv_output = '-o ' + tlv_output
    else:
        tlv_output = ""

    outdir = args.outdir
    if outdir is None:
        outdir = '.'

    endpoint = args.endpoint
    if endpoint is None:
        endpoint = 'https://faas.makerchip.com/function/sandpiper-faas'

    # Zip input files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        if include_files is not None:
            for f in include_files:
                try:
                    file = open(f, 'r');
                except IOError as err:
                    print("Error while opening include file:", err)
                    sys.exit(1)
                try:
                    zip_file.writestr(Path(f).name, file.read())
                except ValueError as err:
                    print("Error while zipping input file:", err)
                    sys.exit(1)

        # Top-level
        try:
            file = open(top, 'r');
        except IOError as err:
            print("Error while opening top-level tlv file:", err)
            sys.exit(1)
        try:
            zip_file.writestr(Path(top).name, file.read())
        except ValueError as err:
            print("Error while zipping input file:", err)
            sys.exit(1)

    try:
        resp = requests.post(
            endpoint,
            files=(
                ('args', (None, "-i " + Path(top).name + ' ' + ' ' + tlv_output + ' ' + additional_args)),# + ' ' \
                          #+ sandpiper_args)),
                ('IAgreeToSLA', (None, "true")),
                ('sv_url_inc', (None, "true" if args.sv_url_inc==True else "false")),
                ('default_includes', (None, "true" if args.default_includes == True else "false")),
                ('context', ('context.zip', zip_buffer.getvalue())),
            ),
            stream=True
        )
    except:
        print("Error while accessing the compile service.")
        sys.exit(1)

    # We can close the zip buffer.
    zip_buffer.close()

    # Open response zip.
    try:
        z = zipfile.ZipFile(BytesIO(resp.content))
    except:
        print("Error while extracting response.")
        sys.exit(int("-100"))

    # Print stderr, stdout
    stderr = z.open('stderr').read().decode('utf-8')
    stdout = z.open('stdout').read().decode('utf-8')

    sys.stderr.write(stderr)
    sys.stdout.write(stdout)

    # Get exit code
    exit_code = z.open('status').read().decode('utf-8')

    # Extract output files to the correct path
    compile_id = resp.headers.get("compile_id")
    for file in z.namelist():
        if file.startswith(compile_id + '/'):
            filename = os.path.relpath(file, compile_id + '/out/')
            source = z.open(file)
            os.makedirs(os.path.dirname(os.path.join(outdir, filename)), exist_ok=True)
            target = open(os.path.join(outdir, filename), "wb")
            with source, target:
                shutil.copyfileobj(source, target)

    # Exit with the received exit code if nothing else has happened.
    sys.exit(int(exit_code))


if __name__ == "__main__":
    run()
