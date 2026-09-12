// Daily water level and licence projection for a monitoring bore.
// Usage: java -cp /app/bore/out Drawdown <data-dir> <output-json>
public class Drawdown {
    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("usage: Drawdown <data-dir> <output-json>");
            System.exit(2);
        }
        // TODO: read the export in args[0], fit, write args[1]
        System.err.println("not implemented");
        System.exit(1);
    }
}
