import java.lang.reflect.Method;
import java.security.Permission;

/*
 * Verifier-owned launcher, never collected from the agent's project. Installs a
 * SecurityManager that blocks process execution and native library loading, then
 * invokes the collected class's main(String[]) by reflection in the same JVM. This
 * closes the route where the collected Java hands the loader a native payload
 * (ProcessBuilder/Runtime.exec, or System.load/loadLibrary), without touching file
 * I/O, which the reference solution needs and which stays fully open.
 */
public class VerifierLaunch {
    public static void main(String[] args) throws Exception {
        System.setSecurityManager(new SecurityManager() {
            @Override public void checkExec(String cmd) {
                throw new SecurityException("process execution is disabled for this run: " + cmd);
            }
            @Override public void checkLink(String lib) {
                throw new SecurityException("native library loading is disabled for this run: " + lib);
            }
            @Override public void checkPermission(Permission perm) { /* allow everything else */ }
            @Override public void checkPermission(Permission perm, Object context) { /* allow everything else */ }
        });
        String className = args[0];
        String[] rest = new String[args.length - 1];
        System.arraycopy(args, 1, rest, 0, rest.length);
        Class<?> cls = Class.forName(className);
        Method m = cls.getMethod("main", String[].class);
        m.invoke(null, (Object) rest);
    }
}
