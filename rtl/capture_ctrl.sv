// Capture controller: arm, fill, trigger, freeze, re-arm.
module capture_ctrl #(
    parameter int DEPTH       = 2048,
    parameter int WIDTH       = 12,
    parameter int PRE_TRIGGER = 512,
    parameter int HYSTERESIS  = 16
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     arm,
    input  logic                     sample_valid,
    input  logic [WIDTH-1:0]         sample,
    input  logic [WIDTH-1:0]         threshold,
    output logic [1:0]               status,
    output logic                     capture_ready,
    output logic [$clog2(DEPTH)-1:0] oldest_addr,  // valid in READY; dump index 0
    input  logic [$clog2(DEPTH)-1:0] rd_addr,
    output logic [WIDTH-1:0]         rd_data
);

    localparam logic [1:0] ST_IDLE      = 2'd0;
    localparam logic [1:0] ST_FILLING   = 2'd1;
    localparam logic [1:0] ST_TRIGGERED = 2'd2;
    localparam logic [1:0] ST_READY     = 2'd3;

    logic [1:0]               state;
    logic                     buf_clear;
    logic                     buf_wr_en;
    logic                     buf_trigger;
    logic                     buf_frozen;
    logic                     buf_pre_filled;
    logic                     trig_arm;
    logic                     trig_pulse;

    assign status        = state;
    assign capture_ready = (state == ST_READY);
    assign buf_clear     = ((state == ST_IDLE) || (state == ST_READY)) && arm;
    assign buf_wr_en     = ((state == ST_FILLING) || (state == ST_TRIGGERED)) &&
                           sample_valid;
    assign trig_arm      = (state == ST_FILLING) && buf_pre_filled;
    assign buf_trigger   = (state == ST_FILLING) && trig_pulse;

    trigger_detect #(
        .WIDTH     (WIDTH),
        .HYSTERESIS(HYSTERESIS)
    ) u_trig (
        .clk          (clk),
        .rst          (rst),
        .arm          (trig_arm),
        .sample_valid (sample_valid),
        .sample       (sample),
        .threshold    (threshold),
        .trigger_pulse(trig_pulse)
    );

    circ_buffer #(
        .DEPTH      (DEPTH),
        .WIDTH      (WIDTH),
        .PRE_TRIGGER(PRE_TRIGGER)
    ) u_buf (
        .clk        (clk),
        .rst        (rst),
        .clear      (buf_clear),
        .wr_en      (buf_wr_en),
        .wr_data    (sample),
        .trigger    (buf_trigger),
        .frozen     (buf_frozen),
        .pre_filled (buf_pre_filled),
        .oldest_addr(oldest_addr),
        .rd_addr    (rd_addr),
        .rd_data    (rd_data)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            state <= ST_IDLE;
        end else begin
            case (state)
                ST_IDLE: begin
                    if (arm)
                        state <= ST_FILLING;
                end
                ST_FILLING: begin
                    if (trig_pulse)
                        state <= ST_TRIGGERED;
                end
                ST_TRIGGERED: begin
                    if (buf_frozen)
                        state <= ST_READY;
                end
                ST_READY: begin
                    if (arm)
                        state <= ST_FILLING;
                end
                default: begin
                    state <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
