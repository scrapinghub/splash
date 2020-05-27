install_manifest=$1
qt_root=`qmake -query QT_INSTALL_PREFIX`
install_root=`realpath $qt_root/..`
prefix_len=${#install_root}

current=`pwd`
pushd $install_root
cat $current/$install_manifest | cut -c $((prefix_len + 2))- | tar --xz -cf $current/build.tar.xz -T -
popd
