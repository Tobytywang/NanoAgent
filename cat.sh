git rev-list --objects HEAD | while read hash path; do
    type=$(/opt/homebrew/bin/git cat-file -t $hash)
    echo "$hash $type $path"
done
