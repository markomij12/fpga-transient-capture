// Falling-edge droop trigger with hysteresis re-arm.
// Pulse is registered: one cycle after the crossing sample_valid.
module trigger_detect #(
    parameter int WIDTH      = 12,
    parameter int HYSTERESIS = 16
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             arm,
    input  logic             sample_valid,
    input  logic [WIDTH-1:0] sample,
    input  logic [WIDTH-1:0] threshold,
    output logic             trigger_pulse
);

    logic [WIDTH:0]      rearm_sum;
    logic [WIDTH-1:0]    rearm_level;
    logic [WIDTH-1:0]    prev_sample;
    logic                have_prev;
    logic                wait_hyst;

    assign rearm_sum   = {1'b0, threshold} + {1'b0, WIDTH'(HYSTERESIS)};
    assign rearm_level = rearm_sum[WIDTH] ? {WIDTH{1'b1}} : rearm_sum[WIDTH-1:0];

    always_ff @(posedge clk) begin
        if (rst) begin
            trigger_pulse <= 1'b0;
            prev_sample   <= '0;
            have_prev     <= 1'b0;
            wait_hyst     <= 1'b0;
        end else begin
            trigger_pulse <= 1'b0;
            if (sample_valid) begin
                if (arm && have_prev && !wait_hyst &&
                    (prev_sample >= threshold) && (sample < threshold)) begin
                    trigger_pulse <= 1'b1;
                    wait_hyst     <= 1'b1;
                end else if (wait_hyst && (sample >= rearm_level)) begin
                    wait_hyst <= 1'b0;
                end
                prev_sample <= sample;
                have_prev   <= 1'b1;
            end
        end
    end

endmodule
