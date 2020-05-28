install_manifest=$1
root_in_archive=$2
archiver=$3

case $archiver in
    txz)
        command='tar --xz -cf'
        extension=tar.xz
        ;;
    7z)
        command='7z a'
        extension=7z
        ;;
    *)
        echo "$archiver is not supported" >&2
        exit
esac

qt_root=`qmake -query QT_INSTALL_PREFIX`

prefix_len=${#qt_root}

work_dir=`mktemp -d`
trap "rm -rf $work_dir" EXIT
if [ -n "$root_in_archive" ];
then
    target_dir=$work_dir/$root_in_archive
    mkdir -p $target_dir
else
    target_dir=$work_dir
fi


cat $install_manifest |
    while read -r source;
    do
        target_file=$target_dir/`echo "$source" | cut -c $((prefix_len + 1))-`
        placement_dir=`dirname $target_file`
        mkdir -p $placement_dir
        cp $source $target_file
    done

result_dir=`dirname $install_manifest`
result=`realpath $result_dir/build.$extension`
rm -rf $result

pushd $work_dir
$command $result ./*
popd
