install_manifest=$1

qt_root=`qmake -query QT_INSTALL_PREFIX`

prefix_len=${#qt_root}

work_dir=`mktemp -d`
trap "rm -rf $work_dir" EXIT

cat $install_manifest |
    while read -r source;
    do
        target_file=$work_dir/`echo "$source" | cut -c $((prefix_len + 1))-`
        placement_dir=`dirname $target_file`
        mkdir -p $placement_dir
        cp $source $target_file
    done

result_dir=`dirname $install_manifest`
result=`realpath $result_dir/build.7z`
rm -rf $result

pushd $work_dir
7z a $result ./*
popd
