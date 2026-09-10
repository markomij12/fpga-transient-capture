// Dump a frozen capture over UART as a TC frame (see host/frame.py).
// Start bit begins the clock after tx_start is sampled in uart_tx IDLE.
module uart_dump #(
    parameter int DEPTH        = 2048,
    parameter int WIDTH        = 12,
    parameter int PRE_TRIGGER  = 512,
    parameter int CLKS_PER_BIT = 868
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     start,
    input  logic [WIDTH-1:0]         rd_data,
    input  logic [$clog2(DEPTH)-1:0] oldest_addr,
    output logic [$clog2(DEPTH)-1:0] rd_addr,
    output logic                     tx,
    output logic                     busy,
    output logic                     done
);

    localparam int AW = $clog2(DEPTH);

    typedef enum logic [2:0] {
        ST_IDLE      = 3'd0,
        ST_READ      = 3'd1,
        ST_ISSUE     = 3'd2,
        ST_WAIT_GO   = 3'd3,
        ST_WAIT_DONE = 3'd4
    } state_t;

    typedef enum logic [1:0] {
        PH_HDR  = 2'd0,
        PH_SAMP = 2'd1,
        PH_XOR  = 2'd2,
        PH_TRL  = 2'd3
    } phase_t;

    state_t        state;
    phase_t        phase;
    logic [2:0]    hdr_i;
    logic [AW-1:0] samp_i;
    logic          samp_hi;
    logic          trl_i;
    logic [7:0]    xor_acc;
    logic [7:0]    tx_data;
    logic          tx_start;
    logic          tx_busy;
    logic [7:0]    issue_byte;
    logic [15:0]   n_u16;
    logic [15:0]   pre_u16;

    assign n_u16  = 16'(DEPTH);
    assign pre_u16 = 16'(PRE_TRIGGER);
    assign busy   = (state != ST_IDLE);

    uart_tx #(
        .CLKS_PER_BIT(CLKS_PER_BIT)
    ) u_tx (
        .clk     (clk),
        .rst     (rst),
        .tx_start(tx_start),
        .tx_data (tx_data),
        .tx      (tx),
        .tx_busy (tx_busy)
    );

    always @(*) begin
        issue_byte = 8'h00;
        case (phase)
            PH_HDR: begin
                case (hdr_i)
                    3'd0:    issue_byte = 8'h54;
                    3'd1:    issue_byte = 8'h43;
                    3'd2:    issue_byte = 8'h01;
                    3'd3:    issue_byte = n_u16[7:0];
                    3'd4:    issue_byte = n_u16[15:8];
                    3'd5:    issue_byte = pre_u16[7:0];
                    default: issue_byte = pre_u16[15:8];
                endcase
            end
            PH_SAMP: begin
                if (!samp_hi)
                    issue_byte = rd_data[7:0];
                else
                    issue_byte = {4'b0000, rd_data[11:8]};
            end
            PH_XOR: issue_byte = xor_acc;
            default: begin
                if (!trl_i)
                    issue_byte = 8'h0D;
                else
                    issue_byte = 8'h0A;
            end
        endcase
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            state     <= ST_IDLE;
            phase     <= PH_HDR;
            hdr_i     <= '0;
            samp_i    <= '0;
            samp_hi   <= 1'b0;
            trl_i     <= 1'b0;
            xor_acc   <= '0;
            tx_data   <= '0;
            tx_start  <= 1'b0;
            rd_addr   <= '0;
            done      <= 1'b0;
        end else begin
            tx_start <= 1'b0;
            done     <= 1'b0;

            case (state)
                ST_IDLE: begin
                    phase   <= PH_HDR;
                    hdr_i   <= '0;
                    samp_i  <= '0;
                    samp_hi <= 1'b0;
                    trl_i   <= 1'b0;
                    xor_acc <= '0;
                    rd_addr <= oldest_addr;
                    if (start)
                        state <= ST_READ;
                end
                ST_READ: begin
                    state <= ST_ISSUE;
                end
                ST_ISSUE: begin
                    tx_data  <= issue_byte;
                    tx_start <= 1'b1;
                    if (phase == PH_HDR || phase == PH_SAMP)
                        xor_acc <= xor_acc ^ issue_byte;
                    state <= ST_WAIT_GO;
                end
                ST_WAIT_GO: begin
                    if (tx_busy)
                        state <= ST_WAIT_DONE;
                end
                ST_WAIT_DONE: begin
                    if (!tx_busy) begin
                        case (phase)
                            PH_HDR: begin
                                if (hdr_i == 3'd6) begin
                                    phase   <= PH_SAMP;
                                    samp_i  <= '0;
                                    samp_hi <= 1'b0;
                                    rd_addr <= oldest_addr;
                                    state   <= ST_READ;
                                end else begin
                                    hdr_i <= hdr_i + 1'b1;
                                    state <= ST_ISSUE;
                                end
                            end
                            PH_SAMP: begin
                                if (!samp_hi) begin
                                    samp_hi <= 1'b1;
                                    state   <= ST_ISSUE;
                                end else if (samp_i == AW'(DEPTH - 1)) begin
                                    phase <= PH_XOR;
                                    state <= ST_ISSUE;
                                end else begin
                                    samp_i  <= samp_i + 1'b1;
                                    samp_hi <= 1'b0;
                                    if (rd_addr == AW'(DEPTH - 1))
                                        rd_addr <= '0;
                                    else
                                        rd_addr <= rd_addr + 1'b1;
                                    state <= ST_READ;
                                end
                            end
                            PH_XOR: begin
                                phase <= PH_TRL;
                                trl_i <= 1'b0;
                                state <= ST_ISSUE;
                            end
                            default: begin
                                if (!trl_i) begin
                                    trl_i <= 1'b1;
                                    state <= ST_ISSUE;
                                end else begin
                                    done  <= 1'b1;
                                    state <= ST_IDLE;
                                end
                            end
                        endcase
                    end
                end
                default: state <= ST_IDLE;
            endcase
        end
    end

endmodule
