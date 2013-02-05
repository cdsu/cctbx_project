#! /bin/sh

# This script executes several commands over a shared SSH-connection.
# It is probably a good idea to have an ssh-agent(1) running (XXX not
# anymore--should only request password once).  XXX Check again with
# notes to see that all this is sane.
#
# Note: A valid AFS token can be obtained by "kinit" followed by
# "aklog".  This avoids the "job being submitted without an AFS token"
# warning.
#
# $Id$

# This script must be run from the SIT directory, which contains the
# .sit_release file, so that the relative PYTHONPATH set by sit_setup
# is valid.  XXX Wouldn't it make sense to have
# /reg/g/psdm/etc/ana_env.sh set an absolute path?  Could find the
# user's release directory from .sit_release file and cd to it in the
# submit.sh script.  No, that's much too slow!
if ! relinfo > /dev/null 2>&1; then
    echo "Must run this script from the SIT release directory" > /dev/stderr
    exit 1
fi

# Path to the chosen pyana script.  This should not need to be
# changed.  According to Marc Messerschmidt following ana-current
# should always be fine, unless one really wants to make sure
# everything is kept at the point where one started developing.  Do
# not use the shell's built-in which(1), which may give a relative
# path.
PYANA=`/usr/bin/which cxi.pyana`
if ! test -x "${PYANA}"; then
    echo "Cannot execute ${PYANA}" > /dev/stderr
    exit 1
fi

# IP-address of a random host that has the scratch directory mounted.
# psexport is preferred over psanafeh, since the latter is not
# accessible from everywhere.
NODE="psexport.slac.stanford.edu"
NODE=`host "${NODE}" | grep "has address" | head -n 1 | cut -d ' ' -f 1`

# Create a directory for temporary files and open a master connection
# to ${NODE}.  Define a function to clean it all up, and call the
# function on interrupt.  Note that the output directory is not
# removed.
tmpdir=`mktemp -d` || exit 1
ssh -fMN -o "ControlPath ${tmpdir}/control.socket" ${NODE}
NODE=`ssh -S "${tmpdir}/control.socket" ${NODE} "hostname -f"`

cleanup_and_exit() {
    ssh -O exit -S "${tmpdir}/control.socket" ${NODE} > /dev/null 2>&1
    rm -fr "${tmpdir}"
    exit ${1}
}
trap "cleanup_and_exit 1" HUP INT QUIT TERM

args=`getopt c:o:p:q:r:x: $*`
if test $? -ne 0; then
    echo "Usage: lsf.sh -c config -r run-num [-o output] [-p num-cpu] [-q queue] [-x exp]" > /dev/stderr
    cleanup_and_exit 1
fi

set -- ${args}
while test ${#} -ge 0; do
    case "${1}" in
        -c)
            cfg="${2}"
            if ! test -r "${cfg}" 2> /dev/null; then
                echo "config must be a readable file" > /dev/stderr
                cleanup_and_exit 1
            fi
            shift
            shift
            ;;

        -o)
            out=`ssh -S "${tmpdir}/control.socket" ${NODE} \
                "cd \"${PWD}\" ; readlink -fn \"${2}\""`
            if ssh -S "${tmpdir}/control.socket" ${NODE} \
                "test -e \"${out}\" -a ! -d \"${out}\" 2> /dev/null"; then
                echo "output exists but is not a directory" > /dev/stderr
                cleanup_and_exit 1
            fi
            ssh -S "${tmpdir}/control.socket" ${NODE} \
                "test -d \"${out}\" 2> /dev/null" ||      \
                echo "output directory will be created" > /dev/stderr
            shift
            shift
            ;;

        -p)
            if ! test "${2}" -gt 0 2> /dev/null; then
                echo "num-cpu must be positive integer" > /dev/stderr
                cleanup_and_exit 1
            fi
            nproc="${2}"
            shift
            shift
            ;;

        -q)
            queue="$2"
            shift
            shift
            ;;

        -r)
            # Set ${run} to a zero-padded, four-digit string
            # representation of the integer.
            if ! test "${2}" -gt 0 2> /dev/null; then
                echo "run-num must be positive integer" > /dev/stderr
                cleanup_and_exit 1
            fi
            run=`echo "${2}" | awk '{ printf("%04d", $1); }'`
            shift
            shift
            ;;

        -x)
            exp="${2}"
            shift
            shift
            ;;

        --)
            shift
            break
            ;;
    esac
done

# Ensure the two mandatory arguments given, and no extraneous
# arguments are present.  XXX Since the corresponding options are not
# optional, they should perhaps be positional arguments instead?
if test -z "${cfg}" -o -z "${run}"; then
    echo "Must specify -c and -r options" > /dev/stderr
    cleanup_and_exit 1
fi
if test "${#}" -gt 0; then
    echo "Extraneous arguments" > /dev/stderr
    cleanup_and_exit 1
fi

# Take ${exp} from the environment unless overridden on the command
# line, and find its absolute path.
test -n "${EXP}" -a -z "${exp}" && exp="${EXP}"
exp=`find "/reg/d/psdm" -maxdepth 2 -name "${exp}"`
if ! ssh -S "${tmpdir}/control.socket" ${NODE} \
    "test -d \"${exp}\" 2> /dev/null"; then
    echo "Could not find experiment subdirectory for ${exp}" > /dev/stderr
    cleanup_and_exit 1
fi

# Construct an absolute path to the directory with the XTC files as
# well as a sorted list of unique stream numbers for ${run}.  XXX May
# need some filtering as suggested by Amedeo Perazzo.
xtc="${exp}/xtc"
streams=`ssh -S "${tmpdir}/control.socket" ${NODE} \
      "ls \"${xtc}\"/e*-r${run}-s* 2> /dev/null"       \
    | sed -e "s:.*-s\([[:digit:]]\+\)-c.*:\1:"     \
    | sort -u                                      \
    | tr -s '\n' ' '`
if test -z "${streams}"; then
    echo "No streams in ${xtc}" > /dev/stderr
    cleanup_and_exit 1
fi

# If ${nproc} is not given on the the command line, fall back on
# num-cpu from ${cfg}.  Otherwise, the number of processes per host
# should be between 7 and 9 according to Marc Messerschmidt.  Using
# only two processors may decrease performance, because distributing
# data from the master process to a single worker process introduces
# overhead.
if test -z "${nproc}"; then
    nproc=`awk -F= '/^[[:space:]]*num-cpu[[:space:]]*=/ { \
                        printf("%d\n", $2);               \
                    }' "${cfg}"`
    test "${nproc}" -gt 0 2> /dev/null || nproc="7"
fi
if ! test ${nproc} != 2 2> /dev/null; then
    echo "Warning: running with two processors makes no sense" > /dev/stderr
fi

# If no queue is given on the command line then submit to default
# queue.
test -z "${queue}" && queue="psfehq"

# Unless specified on the command line, set up the output directory as
# a subdirectory named "results" within the experiment's scratch
# space.  All actual output will be written to the next available
# three-digit trial directory for the run.
if test -z "${out}"; then
    out="${exp}/scratch/results"
fi
out="${out}/r${run}"
trial=`ssh -S "${tmpdir}/control.socket" ${NODE} \
    "mkdir -p \"${out}\" ;                       \
     find \"${out}\" -maxdepth 1                 \
                     -name \"[0-9][0-9][0-9]\"   \
                     -printf \"%f\n\" |          \
     sort -n | tail -n 1"`
if test -z "${trial}"; then
    trial="000"
else
    if test "${trial}" -eq "999"; then
        echo "Error: Trial numbers exhausted" > /dev/stderr
        cleanup_and_exit 1
    fi
    trial=`expr "${trial}" \+ 1 | awk '{ printf("%03d", $1); }'`
fi
out="${out}/${trial}"

# Write a configuration file for the analysis of each stream by
# substituting the directory names with appropriate directories in
# ${out}, and appending the stream number to the base name.  Create a
# run-script for each job, as well as a convenience script to submit
# all the jobs to the queue.  XXX Dump the environment in here, too?
# XXX What about an option to submit all streams to a single host, so
# as to do averaging?
cat > "${tmpdir}/submit.sh" << EOF
#! /bin/sh

OUT="${out}"

EOF
for s in ${streams}; do
    sed -e "s:\([[:alnum:]]\+\)\(_dirname[[:space:]]*=\).*:\1\2 ${out}/\1:"    \
        -e "s:\([[:alnum:]]\+_basename[[:space:]]*=.*\)[[:space:]]*:\1s${s}-:" \
        "${cfg}" > "${tmpdir}/pyana_s${s}.cfg"

    # Process each stream on a single host as a base-1 indexed job,
    # because base-0 will not work.  Allocate no more than ${nproc}
    # processors.  Allow the job to start if at least one processor is
    # available on the host.  Cannot use an indented here-document
    # (<<-), because that would require leading tabs which are not
    # permitted by libtbx.find_clutter.
    i=`expr "${s}" \+ 1`
    cat >> "${tmpdir}/submit.sh" << EOF
bsub -J "r${run}[${i}]" -n "1,${nproc}" -o "\${OUT}/stdout/s${s}.out" \\
    -q "${queue}" -R "span[hosts=1]" "\${OUT}/pyana_s${s}.sh"
EOF
    # limited cores/user:  psfehq.  unlimited: psfehmpiq
    # Create the run-script for stream ${s}.  Fall back on using a
    # single processor if the number of available processors cannot be
    # obtained from the environment or is less than or equal to two.
    cat > "${tmpdir}/pyana_s${s}.sh" << EOF
#! /bin/sh

NPROC=\`printenv LSB_MCPU_HOSTS \
    | awk '{ printf("%d\n", \$2 > 2 ? \$2 : 1); }'\`

test "\${NPROC}" -gt 0 2> /dev/null || NPROC="1"
"${PYANA}" \\
    -c "${out}/pyana_s${s}.cfg" \\
    -p "\${NPROC}" \\
    "${xtc}"/e*-r${run}-s${s}-c*
EOF
    chmod 755 "${tmpdir}/pyana_s${s}.sh"
done
chmod 755 "${tmpdir}/submit.sh"

# Create all directories for the output from the analysis.  This
# eliminates a race condition when run in parallel.
directories=`awk -F=                                    \
    '/^[[:space:]]*[[:alnum:]]+_dirname[[:space:]]*=/ { \
         gsub(/^ /, "", $2);                            \
         gsub(/ $/, "", $2);                            \
         printf("\"%s\"\n", $2);                        \
     }' "${tmpdir}"/pyana_s[0-9][0-9].cfg | sort -u | tr -s '\n' ' '`
ssh -S "${tmpdir}/control.socket" ${NODE} \
    "mkdir -p \"${out}/stdout\" ${directories}"

# Copy the configuration files and the submission script to ${out}.
# Submit the analysis of all streams to the queueing system from
# ${NODE}.
scp -o "ControlPath ${tmpdir}/control.socket" -pq \
    "${cfg}"                         "${NODE}:${out}/pyana.cfg"
scp -o "ControlPath ${tmpdir}/control.socket" -pq \
    "${tmpdir}"/pyana_s[0-9][0-9].cfg             \
    "${tmpdir}"/pyana_s[0-9][0-9].sh              \
    "${tmpdir}/submit.sh"             "${NODE}:${out}"
ssh -S "${tmpdir}/control.socket" ${NODE} \
    "cd \"${PWD}\" && \"${out}/submit.sh\""

echo "Output directory: ${out}"
cleanup_and_exit 0
