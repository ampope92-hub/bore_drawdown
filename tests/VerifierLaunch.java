import java.lang.reflect.Method;
import java.security.Permission;

/*
 * Verifier-owned launcher, never collected from the agent's project. Installs a
 * SecurityManager that blocks process execution and native library loading, then
 * invokes the collected class's main(String[]) by reflection in the same JVM. This
 * closes the route where the collected Java hands the loader a native payload
 * (ProcessBuilder/Runtime.exec, or System.load/loadLibrary), without touching file
 * I/O, which the reference solution needs and which stays fully open.
 *
 * The manager also refuses to be replaced or removed: System.setSecurityManager asks the
 * installed manager for the setSecurityManager permission before it swaps anything, so with
 * that permission refused a call of System.setSecurityManager(null) from the collected class
 * throws instead of clearing the way for a later exec. Constructing a fresh manager is refused
 * the same way, and so is loading anything from sun.misc or sun.reflect, the two packages the
 * JDK's own package.access list restricts and the only unsupported back door left into the
 * JVM's own fields (Unsafe). Nothing in the Java standard library a report needs lives behind
 * any of these three; the JDK's other internal packages stay reachable, since its own service
 * loading (locale data for String.format, for one) goes through them.
 */
public class VerifierLaunch {
    static void refuse(Permission perm) {
        if (!(perm instanceof RuntimePermission)) return;
        String name = perm.getName();
        if (name.equals("setSecurityManager") || name.equals("createSecurityManager")
                || name.startsWith("accessClassInPackage.sun.misc")
                || name.startsWith("accessClassInPackage.sun.reflect")) {
            throw new SecurityException("refused for this run: " + name);
        }
    }

    public static void main(String[] args) throws Exception {
        System.setSecurityManager(new SecurityManager() {
            @Override public void checkExec(String cmd) {
                throw new SecurityException("process execution is disabled for this run: " + cmd);
            }
            @Override public void checkLink(String lib) {
                throw new SecurityException("native library loading is disabled for this run: " + lib);
            }
            @Override public void checkPermission(Permission perm) { refuse(perm); }
            @Override public void checkPermission(Permission perm, Object context) { refuse(perm); }
        });
        String className = args[0];
        String[] rest = new String[args.length - 1];
        System.arraycopy(args, 1, rest, 0, rest.length);
        Class<?> cls = Class.forName(className);
        Method m = cls.getMethod("main", String[].class);
        m.invoke(null, (Object) rest);
    }
}
