/* Minimal native entry point so Finder opens the local UI without Terminal. */
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[PATH_MAX], python[PATH_MAX], script[PATH_MAX];
    const char *suffix = "/LeetCode Coach.app/Contents/MacOS/launcher";
    (void)argc;
    if (!realpath(argv[0], path)) return 1;
    size_t size = strlen(path), tail = strlen(suffix);
    if (size <= tail || strcmp(path + size - tail, suffix) != 0) return 1;
    path[size - tail] = '\0';
    if (snprintf(python, sizeof python, "%s/.venv/bin/python", path) >= sizeof python) return 1;
    if (snprintf(script, sizeof script, "%s/launch_local.py", path) >= sizeof script) return 1;
    execl(python, python, script, (char *)NULL);
    return 1;
}
