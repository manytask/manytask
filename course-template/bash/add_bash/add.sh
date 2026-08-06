# Reference solution (gold). NOT exported — students receive add.sh.template
# renamed to add.sh. Defines `add`, which echoes the sum of its two arguments.
add() {
    echo $(( $1 + $2 ))
}
